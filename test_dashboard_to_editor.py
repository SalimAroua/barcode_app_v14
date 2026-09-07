import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DATABASE_URL"] = "sqlite:///test_dashboard_to_editor.db"
if os.path.exists("test_dashboard_to_editor.db"):
    os.remove("test_dashboard_to_editor.db")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)

import app.models  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.services import receipt_def_service, scan_service  # noqa: E402
from app.models import User  # noqa: E402
from app.views.login_window import LoginWindow  # noqa: E402
from app.controllers.login_controller import LoginController  # noqa: E402

Base.metadata.create_all(engine)
AuthService.create_superuser()
_db = SessionLocal()
receipt_def_service.seed_demo_receipt_if_missing(_db)
_db.close()

qt_app = QApplication([])
results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


login_window = LoginWindow()
login_controller = LoginController(login_window)
login_window.show()
login_window.username.setText("admin")
login_window.password.setText("admin123")
login_window.loginButton.click()

dashboard = login_controller._dashboard_window
dctrl = login_controller._dashboard_controller
check("Dashboard opened", dashboard is not None and dashboard.isVisible())
check("Manage Receipts button exists for SuperUser", hasattr(dashboard, "manageReceiptsButton"))

# Click "Manage Receipt Definitions" exactly like a user would
dashboard.manageReceiptsButton.click()
check("Receipt editor window opened", dctrl._receipt_editor_window is not None and dctrl._receipt_editor_window.isVisible())

editor = dctrl._receipt_editor_window
ectrl = dctrl._receipt_editor_controller

ectrl.on_new_receipt()
editor.nameInput.setText("FULL_LOOP_RECEIPT")
editor.statusCombo.setCurrentText("active")
editor.field_inputs["part_number"].setText("PN-LOOP-001")
ectrl._append_token({"type": "placeholder", "name": "PartNumber"})
ectrl._append_token({"type": "literal", "value": "-SN"})
ectrl._append_token({"type": "placeholder", "name": "SerialNumber"})
editor.serialMinInput.setText("1")
editor.serialMaxInput.setText("9999999")
ectrl.on_save()

# Close the editor the way a user would (X / Close button) -> should refresh dashboard's combo
editor.close()
check("Editor closes", not editor.isVisible())
qt_app.processEvents()  # let the deferred deletion (WA_DeleteOnClose) actually happen
qt_app.processEvents()

# Refresh dashboard's receipt combo (destroyed signal should have fired already)
found = False
for i in range(dashboard.receiptCombo.count()):
    if dashboard.receiptCombo.itemText(i).startswith("FULL_LOOP_RECEIPT"):
        found = True
        dashboard.receiptCombo.setCurrentIndex(i)
        break
check("New receipt appears in dashboard's receipt dropdown after closing editor", found)

# Start a session against it and scan something valid
dashboard.operatorNumberInput.setText("OP99")
dashboard.lineNumberInput.setText("LINEX")
dashboard.startSessionButton.click()
check("Scan window opened for the newly created receipt", dctrl._scan_window is not None)

scan_window = dctrl._scan_window
scan_window.scanInput.setText("PN-LOOP-001-SN0000042")
scan_window.scanInput.returnPressed.emit()
check("Scan against the newly created receipt PASSES", scan_window.resultLabel.text() == "PASS")

scan_window.scanInput.setText("WRONG-VALUE")
scan_window.scanInput.returnPressed.emit()
check("Wrong barcode against new receipt FAILS", scan_window.resultLabel.text().startswith("FAIL"))

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")

os.remove("test_dashboard_to_editor.db")
