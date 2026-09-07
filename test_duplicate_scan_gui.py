"""
GUI smoke test: toggle the "Reject a barcode that has already passed
before" checkbox in the Receipt Editor, save, and confirm it actually
drives duplicate-rejection behavior in a real scan session afterward.

Run with: python test_duplicate_scan_gui.py
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DATABASE_URL"] = "sqlite:///test_duplicate_scan_gui.db"
if os.path.exists("test_duplicate_scan_gui.db"):
    os.remove("test_duplicate_scan_gui.db")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)

from migrations_runner import run_migrations_to_head  # noqa: E402
import app.models  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.models import User, ReceiptDefinition  # noqa: E402
from app.views.receipt_editor_window import ReceiptEditorWindow  # noqa: E402
from app.controllers.receipt_editor_controller import ReceiptEditorController  # noqa: E402

run_migrations_to_head()
AuthService.create_superuser()

qt_app = QApplication([])
results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


db = SessionLocal()
user = db.query(User).first()
db.close()

window = ReceiptEditorWindow()
controller = ReceiptEditorController(window, user)
window.show()

# --- Build a new receipt with the checkbox ON ---
controller.on_new_receipt()
window.nameInput.setText("GUI_DUP_TEST")
window.statusCombo.setCurrentText("active")
controller._append_token({"type": "literal", "value": "SN-"})
controller._append_token({"type": "placeholder", "name": "SerialNumber"})
window.serialMinInput.setText("1")
window.serialMaxInput.setText("999999")
check("Checkbox defaults unchecked on a new receipt", window.preventDuplicatesCheck.isChecked() is False)

window.preventDuplicatesCheck.setChecked(True)
controller.on_save()

db = SessionLocal()
saved = db.query(ReceiptDefinition).filter_by(name="GUI_DUP_TEST").first()
check("Checked state persisted to the database", saved is not None and saved.prevent_duplicate_scans is True)
db.close()

# --- Reselect it from the list, confirm the checkbox reloads correctly ---
controller._load_receipt_list()
found_row = None
for i in range(window.receiptList.count()):
    if window.receiptList.item(i).text().startswith("GUI_DUP_TEST"):
        found_row = i
        break
if found_row is not None:
    window.receiptList.setCurrentRow(found_row)
check("Checkbox reloads as checked when reselecting the receipt", window.preventDuplicatesCheck.isChecked() is True)

# --- Uncheck it and re-save, confirm it flips back off ---
window.preventDuplicatesCheck.setChecked(False)
controller.on_save()
db = SessionLocal()
saved2 = db.query(ReceiptDefinition).filter_by(name="GUI_DUP_TEST").first()
check("Unchecked state persists too", saved2.prevent_duplicate_scans is False)
db.close()

# --- Turn it back on, then confirm it actually drives real scan behavior ---
window.preventDuplicatesCheck.setChecked(True)
controller.on_save()

from app.services import scan_service  # noqa: E402

db = SessionLocal()
rd = db.query(ReceiptDefinition).filter_by(name="GUI_DUP_TEST").first()
session = scan_service.start_scan_session(
    db, started_by_user_id=user.id, receipt_definition_id=rd.id,
    operator_number="OPX", line_number="LX",
)
ev1, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session.id, scanned_value="SN-42")
ev2, _ = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session.id, scanned_value="SN-42")
ev1_ok = ev1.result_ok
ev2_ok = ev2.result_ok
ev2_reason = ev2.failure_reason
db.close()

check("First scan passes after enabling via the checkbox", ev1_ok is True)
check("Repeat scan is rejected after enabling via the checkbox", ev2_ok is False and ev2_reason == "DuplicateScan")

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")

os.remove("test_duplicate_scan_gui.db")
