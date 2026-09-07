"""
GUI smoke test: toggle "Auto-generate batch number" in the Receipt
Editor, confirm the dashboard's Batch field locks/unlocks accordingly,
and that starting a real session produces the auto-generated value.

Run with: python test_batch_numbering_gui.py
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DATABASE_URL"] = "sqlite:///test_batch_gui.db"
if os.path.exists("test_batch_gui.db"):
    os.remove("test_batch_gui.db")

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
from app.views.login_window import LoginWindow  # noqa: E402
from app.controllers.login_controller import LoginController  # noqa: E402

run_migrations_to_head()
AuthService.create_superuser()

qt_app = QApplication([])
results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


db = SessionLocal()
user = db.query(User).first()
db.close()

# --- Build a receipt with auto-generation ON via the real editor UI ---
editor = ReceiptEditorWindow()
ectrl = ReceiptEditorController(editor, user)
editor.show()

ectrl.on_new_receipt()
editor.nameInput.setText("GUI_BATCH_AUTO")
editor.statusCombo.setCurrentText("active")
ectrl._append_token({"type": "literal", "value": "X"})
ectrl._append_token({"type": "placeholder", "name": "SerialNumber"})
editor.serialMinInput.setText("1")
editor.serialMaxInput.setText("999999")
check("Checkbox defaults unchecked on a new receipt", editor.autoGenerateBatchCheck.isChecked() is False)

editor.autoGenerateBatchCheck.setChecked(True)
ectrl.on_save()

db = SessionLocal()
saved = db.query(ReceiptDefinition).filter_by(name="GUI_BATCH_AUTO").first()
check("Checked state persisted", saved is not None and saved.auto_generate_batch_number is True)
db.close()

# --- Now log in and check the dashboard reacts to selecting this receipt ---
login_window = LoginWindow()
login_controller = LoginController(login_window)
login_window.show()
login_window.username.setText("admin")
login_window.password.setText("admin123")
login_window.loginButton.click()

dashboard = login_controller._dashboard_window
dctrl = login_controller._dashboard_controller

dashboard.receiptNameInput.setText("GUI_BATCH_AUTO")
check("Receipt name field resolves the receipt", dashboard.receiptNameInput.text() == "GUI_BATCH_AUTO")
check("Batch field is DISABLED when the selected receipt auto-generates", dashboard.batchLabelInput.isEnabled() is False)

# Switch to a receipt without auto-generation (the seeded demo one, if present) and confirm it unlocks.
dashboard.receiptNameInput.setText("DEMO_RECEIPT")
check("Batch field re-enables for a receipt without auto-generation", dashboard.batchLabelInput.isEnabled() is True)

# --- Start a real session against the auto-batch receipt and check the result ---
dashboard.receiptNameInput.setText("GUI_BATCH_AUTO")
dashboard.operatorNumberInput.setText("OPGUI")
dashboard.lineNumberInput.setText("LINE-GUI")
dashboard.plainLineNumberInput.setText("33")
dashboard.startSessionButton.click()

check("Scan window opened (session started successfully)", dctrl._scan_window is not None)

db = SessionLocal()
from app.models import ScanSession  # noqa: E402
latest = db.query(ScanSession).order_by(ScanSession.id.desc()).first()
batch_label = latest.batch_label if latest else None
db.close()

check("Session got an auto-generated batch label", batch_label is not None and batch_label.isdigit())
check("Auto-generated batch embeds the line code (33)", batch_label is not None and "33" in batch_label)

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")

os.remove("test_batch_gui.db")
