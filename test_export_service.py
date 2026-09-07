"""
Tests for export_service: build real scan data via scan_service, then
export it and read the resulting file back to verify content.

Run with: python test_export_service.py
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///test_export.db"
if os.path.exists("test_export.db"):
    os.remove("test_export.db")

from datetime import datetime, timedelta, timezone  # noqa: E402

import pandas as pd  # noqa: E402
import app.models  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models import ReceiptDefinition, User  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.services import scan_service, export_service  # noqa: E402

Base.metadata.create_all(engine)
AuthService.create_superuser()

results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


db = SessionLocal()
user = db.query(User).first()

rd = ReceiptDefinition(
    name="EXPORT_TEST_RECEIPT", status="active",
    template_tokens=[{"type": "literal", "value": "EXP-"}, {"type": "placeholder", "name": "SerialNumber"}],
    serial_min=1, serial_max=999999, created_at=datetime.now(timezone.utc),
)
db.add(rd)
db.commit()
db.refresh(rd)

session = scan_service.start_scan_session(
    db, started_by_user_id=user.id, receipt_definition_id=rd.id,
    operator_number="OP01", line_number="LINE1", batch_label="BATCH-X",
)

ev1, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session.id, scanned_value="EXP-1")
ev2, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session.id, scanned_value="EXP-2")
ev3, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session.id, scanned_value="WRONG")
scan_service.end_scan_session(db, session.id)
session_id = session.id
rd_id = rd.id
db.close()

# --- 1. Export by session, CSV ---
db = SessionLocal()
count = export_service.export_session(db, session_id, "test_export_session.csv", fmt="csv")
db.close()
check("export_session returns correct count", count == 3)
check("CSV file was created", os.path.exists("test_export_session.csv"))

df = pd.read_csv("test_export_session.csv")
check("CSV has 3 rows", len(df) == 3)
check("CSV has expected columns", {"scanned_value", "result", "failure_reason", "receipt_name", "operator_number"}.issubset(df.columns))
check("Pass/fail results correct", list(df["result"]) == ["PASS", "PASS", "FAIL"])
check("Receipt name joined in correctly", (df["receipt_name"] == "EXPORT_TEST_RECEIPT").all())
check("Operator number joined in correctly", (df["operator_number"] == "OP01").all())
check("Failure reason present for the failing row", df.iloc[2]["failure_reason"] not in ("", None) and not pd.isna(df.iloc[2]["failure_reason"]))

# --- 2. Export by session, XLSX ---
db = SessionLocal()
count_xlsx = export_service.export_session(db, session_id, "test_export_session.xlsx", fmt="xlsx")
db.close()
check("XLSX file was created", os.path.exists("test_export_session.xlsx"))
df_xlsx = pd.read_excel("test_export_session.xlsx")
check("XLSX has same row count as CSV", len(df_xlsx) == 3)

# --- 3. Export by receipt + date range ---
db = SessionLocal()
start = datetime.now(timezone.utc) - timedelta(hours=1)
end = datetime.now(timezone.utc) + timedelta(hours=1)
count_range = export_service.export_receipt_daterange(db, rd_id, start, end, "test_export_range.csv", fmt="csv")
db.close()
check("Date-range export finds all 3 events", count_range == 3)

# Narrow range that excludes everything
db = SessionLocal()
far_start = datetime.now(timezone.utc) + timedelta(days=1)
far_end = datetime.now(timezone.utc) + timedelta(days=2)
count_empty = export_service.export_receipt_daterange(db, rd_id, far_start, far_end, "test_export_empty.csv", fmt="csv")
db.close()
check("Date range outside events returns 0 rows", count_empty == 0)
df_empty = pd.read_csv("test_export_empty.csv")
check("Empty export still produces a valid (header-only) CSV", len(df_empty) == 0)

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")

for f in ["test_export_session.csv", "test_export_session.xlsx", "test_export_range.csv", "test_export_empty.csv", "test_export.db"]:
    if os.path.exists(f):
        os.remove(f)
