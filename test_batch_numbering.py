"""
Tests for auto-generated batch numbers: YYMMDD + Plain Line # + an
ever-incrementing, per-line sequence that never resets and is shared
across every receipt run on that line.

Run with: python test_batch_numbering.py
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///test_batch_numbering.db"
if os.path.exists("test_batch_numbering.db"):
    os.remove("test_batch_numbering.db")

from datetime import datetime  # noqa: E402

from migrations_runner import run_migrations_to_head  # noqa: E402
import app.models  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models import ReceiptDefinition, User  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.services import scan_service, batch_numbering_service  # noqa: E402

run_migrations_to_head()
AuthService.create_superuser()

results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


db = SessionLocal()
user = db.query(User).first()

now = datetime(2026, 9, 7, 10, 30, 0)

# --- 1. Basic format ---
b1 = batch_numbering_service.generate_batch_number(db, "12", now=now)
check("Format matches YYMMDD + Line + 3-digit sequence", b1 == "26090712001")

# --- 2. Sequence increments on the SAME line ---
b2 = batch_numbering_service.generate_batch_number(db, "12", now=now)
check("Second batch on the same line increments the sequence", b2 == "26090712002")

# --- 3. A DIFFERENT line has its own independent sequence, starting at 1 ---
b3 = batch_numbering_service.generate_batch_number(db, "07", now=now)
check("A different line starts its own sequence at 001", b3 == "26090707001")

# Back to line 12 - should continue from where it left off, not affected by line 07
b4 = batch_numbering_service.generate_batch_number(db, "12", now=now)
check("Original line's sequence is unaffected by other lines", b4 == "26090712003")

# --- 4. Sequence does NOT reset on a different date ---
later = datetime(2026, 9, 8, 9, 0, 0)
b5 = batch_numbering_service.generate_batch_number(db, "12", now=later)
check("Sequence keeps counting up on a new day (never resets)", b5 == "26090812004")

# --- 5. A line code longer than 2 digits is used as-is (not truncated) ---
b6 = batch_numbering_service.generate_batch_number(db, "123", now=now)
check("Longer line codes aren't truncated", b6 == "260907123001")

# --- 6. Missing plain_line_number raises a clear error ---
raised = False
try:
    batch_numbering_service.generate_batch_number(db, "", now=now)
except ValueError:
    raised = True
check("Missing Plain Line # raises ValueError", raised)

db.commit()

# --- 7. Integration: a receipt with auto-generation ON ignores the manual batch_label ---
rd_auto = ReceiptDefinition(
    name="BATCH_AUTO", status="active",
    template_tokens=[{"type": "literal", "value": "X"}, {"type": "placeholder", "name": "SerialNumber"}],
    serial_min=1, serial_max=999999,
    auto_generate_batch_number=True,
)
db.add(rd_auto)
db.commit()
db.refresh(rd_auto)

session = scan_service.start_scan_session(
    db, started_by_user_id=user.id, receipt_definition_id=rd_auto.id,
    operator_number="OP1", line_number="LINE-99", plain_line_number="99",
    batch_label="OPERATOR TYPED THIS MANUALLY",
)
check("Auto-generation IGNORES the manually-typed batch label", session.batch_label != "OPERATOR TYPED THIS MANUALLY")
check("Auto-generated batch follows the expected shape (11 digits)",
      session.batch_label is not None and session.batch_label.isdigit() and len(session.batch_label) == 11)
check("Auto-generated batch embeds the correct line code", "99" in session.batch_label)

# --- 8. Integration: a receipt with auto-generation OFF keeps the manual value ---
rd_manual = ReceiptDefinition(
    name="BATCH_MANUAL", status="active",
    template_tokens=[{"type": "literal", "value": "Y"}, {"type": "placeholder", "name": "SerialNumber"}],
    serial_min=1, serial_max=999999,
    auto_generate_batch_number=False,
)
db.add(rd_manual)
db.commit()
db.refresh(rd_manual)

session2 = scan_service.start_scan_session(
    db, started_by_user_id=user.id, receipt_definition_id=rd_manual.id,
    operator_number="OP2", line_number="LINE-01", plain_line_number="01",
    batch_label="MANUAL-BATCH-001",
)
check("Auto-generation OFF keeps the operator's manual batch label", session2.batch_label == "MANUAL-BATCH-001")

# --- 9. Integration: auto-generation ON but no Plain Line # given -> clear error, not a crash ---
raised2 = False
error_message = ""
try:
    scan_service.start_scan_session(
        db, started_by_user_id=user.id, receipt_definition_id=rd_auto.id,
        operator_number="OP3", line_number="LINE-99", plain_line_number="",
    )
except ValueError as e:
    raised2 = True
    error_message = str(e)
check("Starting a session without Plain Line # fails clearly when auto-gen is on", raised2)
check("Error message explains why", "Plain Line" in error_message)

db.close()

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")

os.remove("test_batch_numbering.db")
