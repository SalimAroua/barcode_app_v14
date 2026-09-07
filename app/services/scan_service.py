from datetime import datetime, timezone

from app.domain.exceptions import IncompletePairError
from app.domain.validator import ValidationResult
from app.models import ReceiptDefinition, ScanEvent, ScanSession, ScanUnit
from app.services import batch_numbering_service
from app.services.validation_service import validate


def _utcnow():
    return datetime.now(timezone.utc)


def start_scan_session(db, *, started_by_user_id, receipt_definition_id,
                        operator_number, line_number, plain_line_number=None,
                        batch_label=None):
    rd = db.query(ReceiptDefinition).get(receipt_definition_id)
    if rd is None:
        raise ValueError("ReceiptDefinition not found.")
    if rd.status != "active":
        raise ValueError("ReceiptDefinition is not active.")

    if rd.auto_generate_batch_number:
        # Operator-entered batch (if any) is ignored - this receipt wants
        # a fully automatic YYMMDD+Line+Sequence batch number instead.
        batch_label = batch_numbering_service.generate_batch_number(db, plain_line_number)

    session = ScanSession(
        receipt_definition_id=receipt_definition_id,
        started_by_user_id=started_by_user_id,
        operator_number=operator_number,
        line_number=line_number,
        plain_line_number=plain_line_number,
        batch_label=batch_label,
        is_active=True,
    )
    db.add(session)
    db.commit()
    return session


def end_scan_session(db, scan_session_id):
    session = db.query(ScanSession).get(scan_session_id)
    if session is None:
        raise ValueError("ScanSession not found.")
    session.is_active = False
    session.ended_at = _utcnow()
    db.add(session)
    db.commit()
    return session


def _next_sequence_no(db, scan_session_id):
    last = (
        db.query(ScanEvent)
        .filter(ScanEvent.scan_session_id == scan_session_id)
        .order_by(ScanEvent.sequence_no.desc())
        .first()
    )
    return (last.sequence_no + 1) if last else 1


def _open_unit(db, scan_session_id):
    """The current incomplete unit for this session, if any."""
    return (
        db.query(ScanUnit)
        .filter(ScanUnit.scan_session_id == scan_session_id, ScanUnit.is_complete.is_(False))
        .order_by(ScanUnit.id.desc())
        .first()
    )


def _find_prior_pass(db, receipt_definition_id, scanned_value):
    """Look for any earlier PASSED scan of this exact value against this
    receipt - across all sessions, all time. Only PASSED events count as
    "already used"; a barcode that previously failed can still be scanned
    again normally. Callers should only call this when
    receipt.prevent_duplicate_scans is True.
    """
    return (
        db.query(ScanEvent)
        .filter(
            ScanEvent.receipt_definition_id == receipt_definition_id,
            ScanEvent.scanned_value == scanned_value,
            ScanEvent.result_ok.is_(True),
        )
        .order_by(ScanEvent.id.asc())
        .first()
    )


def record_scan_event(db, *, user_id, scan_session_id, scanned_value, now=None):
    """Validates a scanned value against the session's active receipt and
    records a ScanEvent regardless of pass/fail. If the receipt uses
    companion-label pairing, also manages ScanUnit state:
      - a primary scan opens a new unit (blocked if one is already open)
      - a companion scan completes the open unit (rejected if none is open)
    Returns (ScanEvent, ScanUnit | None).
    """
    now = now or _utcnow()
    session = db.query(ScanSession).get(scan_session_id)
    if session is None:
        raise ValueError("ScanSession not found.")

    rd = db.query(ReceiptDefinition).get(session.receipt_definition_id)
    companion_id = rd.companion_receipt_id

    # Determine if this scan is meant for the primary or the companion
    # receipt when pairing is configured. We try the primary receipt's
    # template first; if that fails to even match and a companion is
    # configured, we try the companion's template.
    is_companion_scan = False
    target_rd = rd
    result = validate(scanned_value, rd, session)

    if not result.ok and companion_id:
        companion_rd = db.query(ReceiptDefinition).get(companion_id)
        companion_result = validate(scanned_value, companion_rd, session)
        if companion_result.ok:
            is_companion_scan = True
            target_rd = companion_rd
            result = companion_result

    # Duplicate-scan check: only meaningful for a value that otherwise
    # passed format validation, and only if this receipt has the option
    # turned on. The rejected attempt still gets logged as a normal failed
    # ScanEvent below (traceability), it just isn't recorded as a pass.
    if result.ok and target_rd.prevent_duplicate_scans:
        prior = _find_prior_pass(db, target_rd.id, scanned_value)
        if prior is not None:
            result = ValidationResult(
                ok=False,
                failure_reason="DuplicateScan",
                details={
                    **result.details,
                    "duplicate_of_event_id": prior.id,
                    "duplicate_of_session_id": prior.scan_session_id,
                    "duplicate_of_scanned_at": prior.created_at.isoformat() if prior.created_at else None,
                },
            )

    seq = _next_sequence_no(db, scan_session_id)
    event = ScanEvent(
        scan_session_id=scan_session_id,
        receipt_definition_id=target_rd.id,
        user_id=user_id,
        sequence_no=seq,
        scanned_value=scanned_value,
        result_ok=result.ok,
        failure_reason=result.failure_reason,
        details_json=result.details,
    )

    unit = None
    open_unit = _open_unit(db, scan_session_id)

    if companion_id:
        if is_companion_scan:
            if open_unit is None:
                # companion scanned but nothing is waiting for it
                event.result_ok = False
                event.failure_reason = "CompanionWithoutPrimary"
                db.add(event)
                db.commit()
                return event, None
            else:
                if result.ok:
                    open_unit.companion_event_id = None  # set once we have event.id, below
                    db.add(event)
                    db.commit()
                    open_unit.companion_event_id = event.id
                    open_unit.is_complete = True
                    open_unit.completed_at = now
                    db.add(open_unit)
                    db.commit()
                    return event, open_unit
                else:
                    db.add(event)
                    db.commit()
                    return event, open_unit
        else:
            # this is a primary-receipt scan
            if result.ok:
                if open_unit is not None:
                    raise IncompletePairError(
                        "A previous unit is still waiting for its companion scan."
                    )
                db.add(event)
                db.commit()
                unit = ScanUnit(
                    scan_session_id=scan_session_id,
                    primary_event_id=event.id,
                    is_complete=False,
                    opened_at=now,
                )
                db.add(unit)
                db.commit()
                return event, unit
            else:
                db.add(event)
                db.commit()
                return event, None

    # No companion pairing configured - just log the event.
    db.add(event)
    db.commit()
    return event, None
