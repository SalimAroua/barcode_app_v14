"""
Tests for the CSV receipt-import service: template mini-syntax parsing,
create-vs-update behavior, companion linking across rows, and error
handling for bad rows.

Run with: python -m tests.test_receipt_import
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///test_receipt_import.db"
if os.path.exists("test_receipt_import.db"):
    os.remove("test_receipt_import.db")

import csv  # noqa: E402
import app.models  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models import ReceiptDefinition  # noqa: E402
from app.services import receipt_import_service as ris  # noqa: E402

Base.metadata.create_all(engine)

results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


COLUMNS = [
    "name", "status", "template", "part_number", "customer_part_number",
    "serial_min", "serial_max", "timestamp_policy",
    "companion_receipt_name", "companion_required", "operator_count", "notes",
]

# --- 1. Template mini-syntax parsing ---
tokens = ris.parse_template_string("<<PartNumber>>-<<CustomerPartNumberNoDot>>-SN<<SerialNumber>>")
check("Parses literal + placeholder tokens correctly", tokens == [
    {"type": "placeholder", "name": "PartNumber"},
    {"type": "literal", "value": "-"},
    {"type": "placeholder", "name": "CustomerPartNumberNoDot"},
    {"type": "literal", "value": "-SN"},
    {"type": "placeholder", "name": "SerialNumber"},
])

tokens2 = ris.parse_template_string(r"LOT-<<regex:LotCode=[A-Z]{2}\d{3}>>-END")
check("Parses a regex token with braces in the pattern without breaking", tokens2 == [
    {"type": "literal", "value": "LOT-"},
    {"type": "regex", "name": "LotCode", "pattern": r"[A-Z]{2}\d{3}"},
    {"type": "literal", "value": "-END"},
])

tokens3 = ris.parse_template_string("<<DT:yyyyMMdd>>")
check("DT:<format> placeholder passes through as one placeholder name", tokens3 == [
    {"type": "placeholder", "name": "DT:yyyyMMdd"},
])

# --- 2. Basic import: create two new receipts ---
write_csv("test_import_1.csv", COLUMNS, [
    {"name": "IMP_A", "status": "active", "template": "<<PartNumber>>-<<SerialNumber>>",
        "part_number": "PN-A", "serial_min": "1", "serial_max": "999999", "operator_count": "3"},
    {"name": "IMP_B", "status": "active", "template": "<<PartNumber>>-<<SerialNumber>>",
     "part_number": "PN-B", "serial_min": "1", "serial_max": "999999"},
])

db = SessionLocal()
report = ris.import_csv(db, "test_import_1.csv")
check("Both new rows created", set(report["created"]) == {"IMP_A", "IMP_B"})
check("No errors on a clean import", report["errors"] == [])
check("Both receipts actually persisted", db.query(ReceiptDefinition).filter(
    ReceiptDefinition.name.in_(["IMP_A", "IMP_B"])).count() == 2)
check("Operator count imported", db.query(ReceiptDefinition).filter_by(name="IMP_A").first().operator_count == 3)
db.close()

# --- 3. Re-importing the same name UPDATES instead of duplicating ---
write_csv("test_import_2.csv", COLUMNS, [
    {"name": "IMP_A", "status": "active", "template": "<<PartNumber>>-<<SerialNumber>>",
     "part_number": "PN-A-CHANGED", "serial_min": "1", "serial_max": "999999"},
])
db = SessionLocal()
report2 = ris.import_csv(db, "test_import_2.csv")
check("Existing name is updated, not created", report2["updated"] == ["IMP_A"] and report2["created"] == [])
updated_row = db.query(ReceiptDefinition).filter_by(name="IMP_A").first()
check("Updated field actually changed", updated_row.part_number == "PN-A-CHANGED")
check("Still exactly one IMP_A row (no duplicate)",
      db.query(ReceiptDefinition).filter_by(name="IMP_A").count() == 1)
db.close()

# --- 4. Companion linking across rows (primary references companion later in file) ---
write_csv("test_import_3.csv", COLUMNS, [
    {"name": "IMP_PRIMARY", "status": "active", "template": "MAIN-<<SerialNumber>>",
     "serial_min": "1", "serial_max": "999999",
     "companion_receipt_name": "IMP_COMPANION", "companion_required": "true"},
    {"name": "IMP_COMPANION", "status": "active", "template": "COMP-<<SerialNumber>>",
     "serial_min": "1", "serial_max": "999999"},
])
db = SessionLocal()
report3 = ris.import_csv(db, "test_import_3.csv")
check("Both companion-pair rows created", set(report3["created"]) == {"IMP_PRIMARY", "IMP_COMPANION"})
primary = db.query(ReceiptDefinition).filter_by(name="IMP_PRIMARY").first()
companion = db.query(ReceiptDefinition).filter_by(name="IMP_COMPANION").first()
check("Companion link resolved by name to the correct id", primary.companion_receipt_id == companion.id)
check("companion_required carried through", primary.companion_required is True)
db.close()

# --- 5. Bad rows are reported, not fatal to the rest of the import ---
write_csv("test_import_4.csv", COLUMNS, [
    {"name": "", "status": "active", "template": "X"},  # missing name
    {"name": "IMP_BAD_REGEX", "status": "active", "template": "<<regex:Bad=[unclosed>>"},
    {"name": "IMP_BAD_SERIAL", "status": "active", "template": "<<SerialNumber>>",
     "serial_min": "not-a-number"},
    {"name": "IMP_GOOD", "status": "active", "template": "GOOD-<<SerialNumber>>",
     "serial_min": "1", "serial_max": "999"},
])
db = SessionLocal()
report4 = ris.import_csv(db, "test_import_4.csv")
check("Good row still imports despite other bad rows", "IMP_GOOD" in report4["created"])
check("Three bad rows reported as errors", len(report4["errors"]) == 3)
check("Bad rows were NOT persisted", db.query(ReceiptDefinition).filter(
    ReceiptDefinition.name.in_(["IMP_BAD_REGEX", "IMP_BAD_SERIAL"])).count() == 0)
db.close()

# --- 6. Missing required column is caught up front ---
write_csv("test_import_5.csv", ["name"], [{"name": "NO_TEMPLATE_COL"}])
db = SessionLocal()
report5 = ris.import_csv(db, "test_import_5.csv")
check("Missing 'template' column caught before processing rows",
      len(report5["errors"]) == 1 and "template" in report5["errors"][0][2])
db.close()

for f in ["test_import_1.csv", "test_import_2.csv", "test_import_3.csv", "test_import_4.csv", "test_import_5.csv"]:
    os.remove(f)
os.remove("test_receipt_import.db")

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")
