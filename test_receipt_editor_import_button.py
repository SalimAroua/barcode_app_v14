"""
GUI smoke test for the "Import CSV..." button in the Receipt Editor:
patches QFileDialog so the automated test can pick a file without a real
file picker, then confirms the import actually lands in the database and
the receipt list refreshes.

Run with: python test_receipt_editor_import_button.py
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DATABASE_URL"] = "sqlite:///test_editor_import.db"
if os.path.exists("test_editor_import.db"):
    os.remove("test_editor_import.db")

import csv  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog  # noqa: E402

QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)

import app.models  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.models import User, ReceiptDefinition  # noqa: E402
from app.views.receipt_editor_window import ReceiptEditorWindow  # noqa: E402
from app.controllers.receipt_editor_controller import ReceiptEditorController  # noqa: E402

Base.metadata.create_all(engine)
AuthService.create_superuser()

qt_app = QApplication([])
results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


COLUMNS = ["name", "status", "template", "part_number", "serial_min", "serial_max", "timestamp_policy"]
with open("button_import_test.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=COLUMNS)
    w.writeheader()
    w.writerow({"name": "BUTTON_IMPORT_TEST", "status": "active",
                "template": "<<PartNumber>>-<<SerialNumber>>", "part_number": "PN-BTN-001",
                "serial_min": "1", "serial_max": "999999", "timestamp_policy": "use_scan_time"})

# Patch the native file picker to return our test CSV without any real dialog.
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("button_import_test.csv", "CSV files (*.csv)"))

db = SessionLocal()
user = db.query(User).first()
db.close()

window = ReceiptEditorWindow()
controller = ReceiptEditorController(window, user)
window.show()

before_count = None
db = SessionLocal()
before_count = db.query(ReceiptDefinition).count()
db.close()

window.importCsvButton.click()

db = SessionLocal()
after_count = db.query(ReceiptDefinition).count()
imported = db.query(ReceiptDefinition).filter_by(name="BUTTON_IMPORT_TEST").first()
db.close()

check("Import added exactly one new receipt", after_count == before_count + 1)
check("Imported receipt has the right part_number", imported is not None and imported.part_number == "PN-BTN-001")

found = any(
    window.receiptList.item(i).text().startswith("BUTTON_IMPORT_TEST")
    for i in range(window.receiptList.count())
)
check("Receipt list refreshes to show the imported receipt", found)

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")

os.remove("button_import_test.csv")
os.remove("test_editor_import.db")
