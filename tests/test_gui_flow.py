"""
Headless GUI smoke test - drives the ACTUAL PySide6 widgets (offscreen
platform) through: login -> dashboard -> start session -> scan (pass) ->
scan (fail) -> end session. This exercises the real controller wiring,
not just the service layer.

Run with: QT_QPA_PLATFORM=offscreen python -m tests.test_gui_flow
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DATABASE_URL"] = "sqlite:///test_gui_flow.db"

if os.path.exists("test_gui_flow.db"):
    os.remove("test_gui_flow.db")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

# Patch QMessageBox so automated clicks don't hang on a real modal .exec()
# waiting for a human to dismiss it. This only affects THIS test process.
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.Ok)

import app.models  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.services import receipt_def_service  # noqa: E402

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


# --- 1. Login screen appears, wrong password rejected ---
login_window = LoginWindow()
login_controller = LoginController(login_window)
login_window.show()

login_window.username.setText("admin")
login_window.password.setText("wrong-password")
login_window.loginButton.click()
check("Wrong password keeps login window open", login_window.isVisible())

# --- 2. Correct login navigates to dashboard ---
login_window.password.setText("admin123")
login_window.loginButton.click()
check("Login window closes on success", not login_window.isVisible())
check("Dashboard window opens on success", login_controller._dashboard_window is not None and login_controller._dashboard_window.isVisible())

dashboard = login_controller._dashboard_window
dctrl = login_controller._dashboard_controller
check("Session follow-up table is present", hasattr(dashboard, "sessionTable"))

check("Dashboard shows admin-only controls for SuperUser", hasattr(dashboard, "manageReceiptsButton"))
check("Top command bar keeps all workspace commands visible", all(
    hasattr(dashboard, name) for name in (
        "loginButton", "manageReceiptsButton", "exportButton",
        "printerSettingsButton", "manageUsersButton", "logoutButton",
    )
))
check("SuperUser commands are enabled", all(button.isEnabled() for button in (
    dashboard.manageReceiptsButton,
    dashboard.exportButton,
    dashboard.printerSettingsButton,
    dashboard.manageUsersButton,
)))
check("Receipt text field is available for barcode scan", hasattr(dashboard, "receiptNameInput") and isinstance(dashboard.receiptNameInput, object))
dashboard.receiptNameInput.setText("DEMO_RECEIPT")

# --- 3. Start a scan session ---
dashboard.operatorNumberInput.setText("OP01")
dashboard.lineNumberInput.setText("FAWL01")
dashboard.plainLineNumberInput.setText("01")
dashboard.batchLabelInput.setText("BATCH-A")
dashboard.startSessionButton.click()

check("Scan window opens after starting session", dctrl._scan_window is not None and dctrl._scan_window.isVisible())

scan_window = dctrl._scan_window
scan_ctrl = dctrl._scan_controller

# --- 4. A passing scan ---
scan_window.scanInput.setText("PN-DEMO-001-CUST123456-SN1000000")
scan_window.scanInput.returnPressed.emit()
check("Passing scan shows PASS", scan_window.resultLabel.text() == "PASS")
check("Input clears after scan", scan_window.scanInput.text() == "")

# --- 5. A failing scan ---
scan_window.scanInput.setText("PN-WRONG-001-CUST123456-SN1000000")
scan_window.scanInput.returnPressed.emit()
check("Failing scan shows FAIL with reason", scan_window.resultLabel.text().startswith("FAIL"))

# --- 6. End session ---
scan_window.endSessionButton.click()
check("Scan window closes on end session", not scan_window.isVisible())

print("\n" + "=" * 80)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 80)
print(f"{n_pass}/{len(results)} passed")

os.remove("test_gui_flow.db")
