import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.domain.exceptions import IncompletePairError, InactiveScanSessionError
from app.domain.validator import ValidationResult
from app.models import ReceiptDefinition, ScanEvent, ScanSession, ScanUnit
from app.models import roles
from app.services import batch_numbering_service
from app.services import printer_service
from app.services.validation_service import validate


def _utcnow():
    return datetime.now(timezone.utc)


def start_scan_session(db, *, started_by_user_id, receipt_definition_id,
                        operator_number, line_number, plain_line_number=None,
                        batch_label=None, operators=None, target_quantity=None):
    rd = db.query(ReceiptDefinition).get(receipt_definition_id)
    if rd is None:
        raise ValueError("ReceiptDefinition not found.")
    if rd.status != "active":
        raise ValueError("ReceiptDefinition is not active.")

    if target_quantity is None:
        target_quantity = rd.target_quantity
    if target_quantity is not None and target_quantity <= 0:
        raise ValueError("Target quantity must be greater than zero.")

    if rd.auto_generate_batch_number:
        # Operator-entered batch (if any) is ignored - this receipt wants
        # a fully automatic YYMMDD+Line+Sequence batch number instead.
        batch_label = batch_numbering_service.generate_batch_number(db, plain_line_number)

    session = ScanSession(
        receipt_definition_id=receipt_definition_id,
        started_by_user_id=started_by_user_id,
        operator_number=operator_number,
        operators=operators,
        line_number=line_number,
        plain_line_number=plain_line_number,
        batch_label=batch_label,
        target_quantity=target_quantity,
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


def _count_successful_scans(db, scan_session_id):
    return (
        db.query(ScanEvent)
        .filter(ScanEvent.scan_session_id == scan_session_id, ScanEvent.result_ok.is_(True))
        .count()
    )


def get_scan_session_status(db, scan_session_id):
    session = db.query(ScanSession).get(scan_session_id)
    if session is None:
        raise ValueError("ScanSession not found.")
    return session, _count_successful_scans(db, scan_session_id)


def _render_label_output(session, receipt_definition):
    template_path = receipt_definition.template_file_path
    batch_label = session.batch_label or ""
    template_text = ""

    if template_path and os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as fh:
            template_text = fh.read()
    else:
        template_text = (
            "^XA\n"
            "^CF0,36\n"
            "^FO40,40^FDBatch: {batch_label}^FS\n"
            "^FO40,90^FDReceipt: {receipt_name}^FS\n"
            "^FO40,140^FDOperator: {operator_number}^FS\n"
            "^FO40,190^FDLine: {line_number}^FS\n"
            "^FO40,240^FDTarget: {target_quantity}^FS\n"
            "^XZ\n"
        )

    values = {
        "batch_label": batch_label,
        "receipt_name": receipt_definition.name,
        "operator_number": session.operator_number,
        "line_number": session.line_number,
        "plain_line_number": session.plain_line_number or "",
        "operators": session.operators or "",
        "target_quantity": session.target_quantity or "",
    }
    rendered = template_text.format_map({**{k: "" for k in values.keys()}, **values})
    if "^XA" not in rendered.upper():
        rendered = _plain_text_to_zpl(rendered)

    tmp_dir = tempfile.gettempdir()
    output_path = os.path.join(tmp_dir, f"printed_batch_{session.id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}.zpl")
    Path(output_path).write_text(rendered, encoding="utf-8")
    return output_path


def _plain_text_to_zpl(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    commands = ["^XA", "^CF0,36"]
    for index, line in enumerate(lines):
        escaped = line.replace("^", " ").replace("~", " ")
        commands.append(f"^FO40,{40 + index * 50}^FD{escaped}^FS")
    commands.append("^XZ")
    return "\n".join(commands) + "\n"


def _send_zpl_to_printer(output_path):
    zpl_bytes = Path(output_path).read_bytes()
    return printer_service.send_zpl(zpl_bytes)


def _print_label(session, receipt_definition):
    output_path = _render_label_output(session, receipt_definition)
    _send_zpl_to_printer(output_path)
    return output_path


def reprint_label(db, *, scan_session_id, requesting_role):
    if requesting_role not in roles.CAN_MANAGE_RECEIPTS:
        raise PermissionError("Only Admin or SuperUser can reprint a label.")

    session = db.query(ScanSession).get(scan_session_id)
    if session is None:
        raise ValueError("ScanSession not found.")
    if session.is_active or not session.printed_label_path:
        raise ValueError("A completed session with a printed label is required.")

    receipt_definition = db.query(ReceiptDefinition).get(session.receipt_definition_id)
    session.printed_label_path = _print_label(session, receipt_definition)
    db.add(session)
    db.commit()
    return session.printed_label_path


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
    if not session.is_active:
        raise InactiveScanSessionError("This scan session is complete. Scanning has been stopped.")

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

    # We do not commit the event immediately if a later step needs session
    # state from the same transaction, but we do commit before checking target
    # completion so the count reflects the real persisted state.
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

    if (event.result_ok and session.is_active and session.target_quantity is not None
            and session.printed_label_path is None):
        successful_count = _count_successful_scans(db, scan_session_id)
        if successful_count >= session.target_quantity:
            session.printed_label_path = _print_label(session, rd)
            session.is_active = False
            session.ended_at = _utcnow()
            db.add(session)
            db.commit()

    return event, None
