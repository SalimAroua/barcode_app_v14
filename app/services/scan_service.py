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

    operator_values = [value.strip() for value in (operators or "").split(";") if value.strip()]
    if len(operator_values) > (rd.operator_count or 1):
        raise ValueError(f"This receipt allows a maximum of {rd.operator_count or 1} operators.")

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


def _count_completed_units(db, scan_session_id):
    return (
        db.query(ScanUnit)
        .filter(
            ScanUnit.scan_session_id == scan_session_id,
            ScanUnit.is_complete.is_(True),
        )
        .count()
    )


def _count_session_progress(db, session):
    if (
        session.receipt_definition
        and session.receipt_definition.companion_receipt_id
        and session.receipt_definition.companion_required
    ):
        return _count_completed_units(db, session.id)
    return _count_successful_scans(db, session.id)


def _complete_target_if_reached(db, session, receipt_definition):
    """Print once the required number of complete units reaches the target."""
    if not session.is_active or session.target_quantity is None or session.printed_label_path:
        return
    if _count_session_progress(db, session) < session.target_quantity:
        return
    session.printed_label_path = _print_label(session, receipt_definition)
    session.is_active = False
    session.ended_at = _utcnow()
    db.add(session)
    db.commit()


def get_scan_session_status(db, scan_session_id):
    session = db.query(ScanSession).get(scan_session_id)
    if session is None:
        raise ValueError("ScanSession not found.")
    receipt = db.query(ReceiptDefinition).get(session.receipt_definition_id)
    session.receipt_definition = receipt
    return session, _count_session_progress(db, session)


def get_scan_session_metrics(db, scan_session_id):
    session = db.query(ScanSession).get(scan_session_id)
    if session is None:
        raise ValueError("ScanSession not found.")
    receipt = db.query(ReceiptDefinition).get(session.receipt_definition_id)
    events = db.query(ScanEvent).filter(ScanEvent.scan_session_id == scan_session_id).all()
    ok_count = sum(1 for event in events if event.result_ok)
    nok_count = len(events) - ok_count
    end_time = session.ended_at if not session.is_active and session.ended_at else _utcnow()
    started_at = session.started_at or end_time
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    cycle_seconds = max(0, int((end_time - started_at).total_seconds()))
    return {
        "receipt_name": receipt.name if receipt else "",
        "part_number": receipt.part_number if receipt else "",
        "ok_count": ok_count,
        "nok_count": nok_count,
        "tested_count": len(events),
        "cycle_seconds": cycle_seconds,
    }


def list_scan_session_metrics(db):
    sessions = db.query(ScanSession).order_by(ScanSession.id.desc()).all()
    metrics = []
    for session in sessions:
        receipt = db.query(ReceiptDefinition).get(session.receipt_definition_id)
        events = (
            db.query(ScanEvent)
            .filter(ScanEvent.scan_session_id == session.id)
            .all()
        )
        ok_count = sum(1 for event in events if event.result_ok)
        end_time = session.ended_at if not session.is_active and session.ended_at else _utcnow()
        started_at = session.started_at or end_time
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        metrics.append({
            "session_id": session.id,
            "receipt_name": receipt.name if receipt else "",
            "part_number": receipt.part_number if receipt else "",
            "ok_count": ok_count,
            "nok_count": len(events) - ok_count,
            "tested_count": len(events),
            "cycle_seconds": max(0, int((end_time - started_at).total_seconds())),
            "started_at": started_at,
            "ended_at": session.ended_at,
            "is_active": bool(session.is_active),
        })
    return metrics


def get_dashboard_kpis(db):
    sessions = db.query(ScanSession).order_by(ScanSession.id.desc()).all()
    total_tested = total_ok = total_completed = 0
    total_cycle_seconds = 0
    active_target = None
    active_elapsed_seconds = 0

    for session in sessions:
        receipt = db.query(ReceiptDefinition).get(session.receipt_definition_id)
        events = db.query(ScanEvent).filter(ScanEvent.scan_session_id == session.id).all()
        ok_count = sum(1 for event in events if event.result_ok)
        total_tested += len(events)
        total_ok += ok_count
        if receipt and receipt.companion_receipt_id and receipt.companion_required:
            completed = _count_completed_units(db, session.id)
        else:
            completed = ok_count
        total_completed += completed

        end_time = session.ended_at if not session.is_active and session.ended_at else _utcnow()
        started_at = session.started_at or end_time
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        total_cycle_seconds += max(0, int((end_time - started_at).total_seconds()))

        if active_target is None and session.is_active and session.target_quantity:
            active_target = (session, completed)
            active_elapsed_seconds = max(0, int((end_time - started_at).total_seconds()))

    total_nok = total_tested - total_ok
    first_pass_yield = (total_ok / total_tested * 100) if total_tested else 0
    nok_rate = (total_nok / total_tested * 100) if total_tested else 0
    average_takt_seconds = total_cycle_seconds / total_completed if total_completed else 0
    parts_per_hour = total_completed / (total_cycle_seconds / 3600) if total_cycle_seconds else 0

    target_text = "-"
    eta_text = "-"
    if active_target:
        session, completed = active_target
        target_text = f"{completed} / {session.target_quantity}"
        if completed and session.started_at:
            elapsed = max(1, active_elapsed_seconds)
            rate = completed / elapsed
            remaining = max(0, session.target_quantity - completed)
            eta_text = _format_duration(int(remaining / rate)) if rate else "-"

    return {
        "tested_count": total_tested,
        "ok_count": total_ok,
        "nok_count": total_nok,
        "first_pass_yield": first_pass_yield,
        "nok_rate": nok_rate,
        "average_takt_seconds": average_takt_seconds,
        "parts_per_hour": parts_per_hour,
        "target_progress": target_text,
        "eta": eta_text,
    }


def _format_duration(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


import re

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def _session_operators(session):
    """Return the session's Operator 1..10 values in a stable list.

    The dashboard stores all entered operators as a semicolon-separated
    string. Operator 1 is also mirrored by ``session.operator_number`` for
    backward compatibility with the older session model.
    """
    raw = session.operators or ""
    operators = [value.strip() for value in raw.split(";") if value.strip()]
    if not operators and session.operator_number:
        operators = [str(session.operator_number).strip()]
    return operators[:10]


# Production-step names used by the identification-card ZPL template. The
# first seven steps map to Operator 1..7. Generic OPERATOR_1..10 aliases are
# also exposed so a template can use all ten operator slots when required.
_STEP_OPERATOR_MAP = {
    "COUPEUR": 1,
    "GL_COUPE": 2,
    "INSERTION_FILS": 3,
    "ENRUBANAGE": 4,
    "EOL": 5,
    "INSERTION_CLIPS": 6,
    "GL_ASSEMBLAGE": 7,
}


def _operator_label_values(session):
    """Build placeholder values for operator/production-step traceability."""
    operators = _session_operators(session)
    started_at = session.started_at or _utcnow()
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    # Keep the date simple and human-readable for the identification card.
    date_value = started_at.strftime("%d/%m/%Y")
    datetime_value = started_at.strftime("%d/%m/%Y %H:%M:%S")
    values = {}

    for index in range(1, 11):
        operator = operators[index - 1] if index <= len(operators) else ""
        # Several intuitive aliases are accepted so existing/new ZPL files do
        # not have to use one exact spelling.
        values[f"OPERATOR_{index}"] = operator
        values[f"OPERATOR{index}"] = operator
        values[f"OPERATOR_{index}_NOM"] = operator
        values[f"OPERATOR{index}_NOM"] = operator
        values[f"OPERATOR_{index}_NAME"] = operator
        values[f"OPERATOR{index}_NAME"] = operator
        values[f"OPERATOR_{index}_DATE"] = date_value
        values[f"OPERATOR{index}_DATE"] = date_value
        values[f"OPERATOR_{index}_DATETIME"] = datetime_value
        values[f"OPERATOR{index}_DATETIME"] = datetime_value

    for step_name, operator_index in _STEP_OPERATOR_MAP.items():
        operator = operators[operator_index - 1] if operator_index <= len(operators) else ""
        values[f"{step_name}_NOM"] = operator
        values[f"{step_name}_NAME"] = operator
        values[f"{step_name}_DATE"] = date_value
        values[f"{step_name}_DATETIME"] = datetime_value

    return values


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
        # Aliases for the {{DOUBLE_BRACE}} template convention.
        "REFERENCE": receipt_definition.part_number or receipt_definition.name or "",
        "QTE": session.target_quantity or receipt_definition.quantity_text or "",
    }
    values.update(_operator_label_values(session))

    if "{{" in template_text:
        # {{name}} convention. Do not use str.format_map here: Python treats
        # doubled braces as escaped literal braces.
        def _replace(match):
            key = match.group(1)
            if key in values:
                return str(values[key])
            return match.group(0)

        rendered = _PLACEHOLDER_RE.sub(_replace, template_text)
    else:
        # {field} convention (built-in fallback and older custom templates).
        rendered = template_text.format_map({**{k: "" for k in values.keys()}, **values})

    if "^XA" not in rendered.upper():
        rendered = _plain_text_to_zpl(rendered)

    # Prevent operator/receipt data from accidentally becoming ZPL commands.
    rendered = rendered.replace("\r\n", "\n").replace("\r", "\n")
    rendered = rendered.replace("^XA", "^XA").replace("^XZ", "^XZ")

    tmp_dir = tempfile.gettempdir()
    output_path = os.path.join(
        tmp_dir,
        f"printed_batch_{session.id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}.zpl",
    )
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


def render_label_for_preview(session, receipt_definition):
    """Render the exact concrete ZPL that the print path would send, but do not print it."""
    return _render_label_output(session, receipt_definition)


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


def record_scan_event(
    db, *, user_id, scan_session_id, scanned_value, now=None, expected_receipt=None
):
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
    companion_id = rd.companion_receipt_id if rd.companion_required else None

    # Determine if this scan is meant for the primary or the companion
    # receipt when pairing is configured. We try the primary receipt's
    # template first; if that fails to even match and a companion is
    # configured, we try the companion's template.
    is_companion_scan = False
    target_rd = rd
    if expected_receipt == "companion" and companion_id:
        target_rd = db.query(ReceiptDefinition).get(companion_id)
        is_companion_scan = True
        result = validate(scanned_value, target_rd, session)
    else:
        result = validate(scanned_value, rd, session)
        if not result.ok and companion_id and expected_receipt is None:
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
                    _complete_target_if_reached(db, session, rd)
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

    if event.result_ok:
        session.receipt_definition = rd
        _complete_target_if_reached(db, session, rd)

    return event, None
