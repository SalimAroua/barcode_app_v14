"""
Regression test for a real bug found in main.py: constructing a
controller without keeping a reference to it (e.g. `LoginController(window)`
instead of `login_controller = LoginController(window)`) lets Python's
garbage collector destroy the controller shortly after creation, which
silently breaks the button's click handling - clicking Login then does
nothing at all (no popup, no window change, no error).

This test asserts the FIXED pattern (reference kept + gc.collect() forced)
still works, so a future refactor can't reintroduce the bug unnoticed.

Run with: python -m tests.test_regression_controller_gc
"""
import os
import gc

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DATABASE_URL"] = "sqlite:///test_regression_controller_gc.db"
if os.path.exists("test_regression_controller_gc.db"):
    os.remove("test_regression_controller_gc.db")

from PySide6.QtWidgets import QApplication  # noqa: E402
import app.models  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.views.login_window import LoginWindow  # noqa: E402
from app.controllers.login_controller import LoginController  # noqa: E402

Base.metadata.create_all(engine)
AuthService.create_superuser()

qt_app = QApplication([])

window = LoginWindow()

# The fix: keep the reference alive (matches main.py).
login_controller = LoginController(window)

window.show()

# Force a collection pass to simulate what can happen naturally over time
# if nothing else were holding a reference.
gc.collect()

window.username.setText("admin")
window.password.setText("admin123")
window.loginButton.click()

ok = (not window.isVisible()) and (login_controller._dashboard_window is not None)
print("PASS" if ok else "FAIL", "- login button still works after gc.collect() with reference kept")

os.remove("test_regression_controller_gc.db")

if not ok:
    raise SystemExit(1)
