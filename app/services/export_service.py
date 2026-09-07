"""
Exports scan history (ScanEvent rows) to CSV or XLSX, either for one
ScanSession or for a ReceiptDefinition within a date range.
"""
import json

import pandas as pd

from app.models import ReceiptDefinition, ScanEvent, ScanSession, User


def _rows_to_dataframe(db, events):
    """Turns a list of ScanEvent rows into a flat, human-readable DataFrame
    (joins in session/receipt/user info rather than leaving raw ids)."""
    session_cache = {}
    receipt_cache = {}
    user_cache = {}

    records = []
    for ev in events:
        if ev.scan_session_id not in session_cache:
            session_cache[ev.scan_session_id] = db.query(ScanSession).get(ev.scan_session_id)
        session = session_cache[ev.scan_session_id]

        if ev.receipt_definition_id not in receipt_cache:
            receipt_cache[ev.receipt_definition_id] = db.query(ReceiptDefinition).get(ev.receipt_definition_id)
        receipt = receipt_cache[ev.receipt_definition_id]

        if ev.user_id not in user_cache:
            user_cache[ev.user_id] = db.query(User).get(ev.user_id)
        user = user_cache[ev.user_id]

        records.append({
            "scan_event_id": ev.id,
            "sequence_no": ev.sequence_no,
            "scanned_value": ev.scanned_value,
            "result": "PASS" if ev.result_ok else "FAIL",
            "failure_reason": ev.failure_reason or "",
            "details": json.dumps(ev.details_json) if ev.details_json else "",
            "created_at": ev.created_at.isoformat() if ev.created_at else "",
            "scan_session_id": ev.scan_session_id,
            "operator_number": session.operator_number if session else "",
            "operators": session.operators if session else "",
            "line_number": session.line_number if session else "",
            "batch_label": session.batch_label if session else "",
            "receipt_name": receipt.name if receipt else "",
            "scanned_by_username": user.username if user else "",
        })

    columns = [
        "scan_event_id", "sequence_no", "created_at", "result", "failure_reason",
        "scanned_value", "details", "receipt_name", "scan_session_id",
        "operator_number", "operators", "line_number", "batch_label", "scanned_by_username",
    ]
    return pd.DataFrame.from_records(records, columns=columns)


def get_events_for_session(db, scan_session_id):
    return (
        db.query(ScanEvent)
        .filter(ScanEvent.scan_session_id == scan_session_id)
        .order_by(ScanEvent.sequence_no)
        .all()
    )


def get_events_for_receipt_daterange(db, receipt_id, start_dt, end_dt):
    return (
        db.query(ScanEvent)
        .filter(
            ScanEvent.receipt_definition_id == receipt_id,
            ScanEvent.created_at >= start_dt,
            ScanEvent.created_at <= end_dt,
        )
        .order_by(ScanEvent.created_at)
        .all()
    )


def export_session(db, scan_session_id, file_path, fmt="csv"):
    events = get_events_for_session(db, scan_session_id)
    df = _rows_to_dataframe(db, events)
    _write(df, file_path, fmt)
    return len(events)


def export_receipt_daterange(db, receipt_id, start_dt, end_dt, file_path, fmt="csv"):
    events = get_events_for_receipt_daterange(db, receipt_id, start_dt, end_dt)
    df = _rows_to_dataframe(db, events)
    _write(df, file_path, fmt)
    return len(events)


def _write(df, file_path, fmt):
    if fmt == "csv":
        df.to_csv(file_path, index=False)
    elif fmt == "xlsx":
        df.to_excel(file_path, index=False, engine="openpyxl")
    else:
        raise ValueError(f"Unknown export format: {fmt!r}")
