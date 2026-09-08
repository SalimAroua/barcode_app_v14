"""
Tests for duplicate-scan prevention: opt-in per ReceiptDefinition, checked
against ALL prior PASSED scans for that receipt (any session, any time -
not just the current session), while the rejected attempt itself is still
logged as a normal failed ScanEvent for traceability.

Run with: python -m tests.test_duplicate_scan_detection
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///test_duplicate_scan.db"
if os.path.exists("test_duplicate_scan.db"):
    os.remove("test_duplicate_scan.db")

from datetime import datetime, timezone  # noqa: E402

from migrations_runner import run_migrations_to_head  # noqa: E402
import app.models  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models import ReceiptDefinition, User  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.services import scan_service  # noqa: E402

run_migrations_to_head()
AuthService.create_superuser()

results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


db = SessionLocal()
user = db.query(User).first()

# --- Receipt WITH duplicate prevention enabled ---
rd_strict = ReceiptDefinition(
    name="DUP_STRICT", status="active",
    template_tokens=[{"type": "literal", "value": "SN-"}, {"type": "placeholder", "name": "SerialNumber"}],
    serial_min=1, serial_max=999999,
    prevent_duplicate_scans=True,
    created_at=datetime.now(timezone.utc),
)
db.add(rd_strict)

# --- Receipt WITHOUT duplicate prevention (default off) ---
rd_lenient = ReceiptDefinition(
    name="DUP_LENIENT", status="active",
    template_tokens=[{"type": "literal", "value": "SN-"}, {"type": "placeholder", "name": "SerialNumber"}],
    serial_min=1, serial_max=999999,
    created_at=datetime.now(timezone.utc),
)
db.add(rd_lenient)
db.commit()
db.refresh(rd_strict)
db.refresh(rd_lenient)

# --- 1. Default is off ---
check("prevent_duplicate_scans defaults to False", rd_lenient.prevent_duplicate_scans is False)
check("Explicitly-set receipt has it True", rd_strict.prevent_duplicate_scans is True)

# --- 2. On the STRICT receipt: same value twice, second is rejected ---
session1 = scan_service.start_scan_session(
    db, started_by_user_id=user.id, receipt_definition_id=rd_strict.id,
    operator_number="OP1", line_number="L1",
)
ev1, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session1.id, scanned_value="SN-100")
check("First scan of a value passes", ev1.result_ok is True)

ev2, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session1.id, scanned_value="SN-100")
check("Second scan of the SAME value is rejected", ev2.result_ok is False)
check("Rejection reason is DuplicateScan", ev2.failure_reason == "DuplicateScan")
check("Duplicate details reference the original passing event", ev2.details_json.get("duplicate_of_event_id") == ev1.id)

# --- 3. Duplicate check is ALL-TIME, not scoped to the current session ---
scan_service.end_scan_session(db, session1.id)
session2 = scan_service.start_scan_session(
    db, started_by_user_id=user.id, receipt_definition_id=rd_strict.id,
    operator_number="OP2", line_number="L2",
)
ev3, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session2.id, scanned_value="SN-100")
check("Same value rejected even in a BRAND NEW session (all-time scope)", ev3.result_ok is False)
check("Still reports DuplicateScan in the new session", ev3.failure_reason == "DuplicateScan")

# A different value in the new session should still pass fine.
ev4, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session2.id, scanned_value="SN-200")
check("A genuinely different value still passes", ev4.result_ok is True)

# --- 4. Only PASSED scans count as "already used" - a failed attempt doesn't block a real scan ---
ev5, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session2.id, scanned_value="NOT-EVEN-VALID-FORMAT")
check("A format-invalid scan just fails normally (not a duplicate)", ev5.result_ok is False and ev5.failure_reason != "DuplicateScan")

ev6, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session2.id, scanned_value="SN-300")
check("A never-before-passed value still scans fine after an unrelated failure", ev6.result_ok is True)

# Now scan SN-300 again - it previously PASSED (ev6), so a repeat should be rejected.
ev7, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session2.id, scanned_value="SN-300")
check("Repeating a value that previously passed is rejected", ev7.result_ok is False and ev7.failure_reason == "DuplicateScan")

# --- 5. Every duplicate attempt is still logged in full, for traceability ---
all_events_for_sn100 = (
    db.query(app.models.ScanEvent)
    .filter_by(receipt_definition_id=rd_strict.id, scanned_value="SN-100")
    .count()
)
check("Every attempt (the original pass AND both rejected repeats) is logged (traceability)",
      all_events_for_sn100 == 3)

# --- 6. The LENIENT receipt (option off) allows the same value repeatedly ---
session3 = scan_service.start_scan_session(
    db, started_by_user_id=user.id, receipt_definition_id=rd_lenient.id,
    operator_number="OP3", line_number="L3",
)
ev8, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session3.id, scanned_value="SN-999")
ev9, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session3.id, scanned_value="SN-999")
check("Lenient receipt: first scan passes", ev8.result_ok is True)
check("Lenient receipt: repeat ALSO passes (feature is opt-in, off by default)", ev9.result_ok is True)

db.close()

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")

os.remove("test_duplicate_scan.db")
