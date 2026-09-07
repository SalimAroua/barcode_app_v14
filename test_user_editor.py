"""
Headless GUI smoke test for the User editor: create a new Operator
account, confirm it can log in, edit its role, reset its password, and
confirm the safety rails (duplicate username, last-SuperUser protection,
self-lockout protection) actually hold.

Run with: python test_user_editor.py
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DATABASE_URL"] = "sqlite:///test_user_editor.db"
if os.path.exists("test_user_editor.db"):
    os.remove("test_user_editor.db")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)

import app.models  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.models import User  # noqa: E402

from app.views.user_editor_window import UserEditorWindow  # noqa: E402
from app.controllers.user_editor_controller import UserEditorController  # noqa: E402

Base.metadata.create_all(engine)
AuthService.create_superuser()

qt_app = QApplication([])
results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


db = SessionLocal()
admin_user = db.query(User).filter_by(username="admin").first()
db.close()

window = UserEditorWindow()
controller = UserEditorController(window, admin_user)
window.show()

# --- 1. Create a new Operator account ---
controller.on_new_user()
window.usernameInput.setText("jdoe")
window.fullnameInput.setText("Jane Doe")
window.roleCombo.setCurrentText("Operator")
window.activeCheck.setChecked(True)
window.passwordInput.setText("secret123")
window.passwordConfirmInput.setText("secret123")
controller.on_save()

db = SessionLocal()
jdoe = db.query(User).filter_by(username="jdoe").first()
check("New user persisted", jdoe is not None)
check("Role persisted correctly", jdoe is not None and jdoe.role == "Operator")
check("Active by default", jdoe is not None and jdoe.active is True)
db.close()

check("New user can log in with the password just set", AuthService.login("jdoe", "secret123") is not None)
check("Wrong password is rejected", AuthService.login("jdoe", "wrong") is None)

# --- 2. Mismatched password/confirm is rejected ---
controller.on_new_user()
window.usernameInput.setText("baduser")
window.passwordInput.setText("abc123")
window.passwordConfirmInput.setText("different")
controller.on_save()
db = SessionLocal()
check("Mismatched password/confirm blocks user creation", db.query(User).filter_by(username="baduser").first() is None)
db.close()

# --- 3. Duplicate username rejected ---
controller.on_new_user()
window.usernameInput.setText("jdoe")  # already exists
window.passwordInput.setText("x")
window.passwordConfirmInput.setText("x")
controller.on_save()
db = SessionLocal()
check("Duplicate username rejected (still exactly one 'jdoe')",
      db.query(User).filter_by(username="jdoe").count() == 1)
db.close()

# --- 4. Edit jdoe: change role, reset password ---
controller._load_user_list()
found_row = None
for i in range(window.userList.count()):
    if window.userList.item(i).text().startswith("jdoe"):
        found_row = i
        break
check("jdoe appears in the user list", found_row is not None)

if found_row is not None:
    window.userList.setCurrentRow(found_row)
    check("Username field is locked when editing", not window.usernameInput.isEnabled())
    window.roleCombo.setCurrentText("Admin")
    window.passwordInput.setText("newpass456")
    window.passwordConfirmInput.setText("newpass456")
    controller.on_save()

    db = SessionLocal()
    jdoe2 = db.query(User).filter_by(username="jdoe").first()
    check("Role updated to Admin", jdoe2 is not None and jdoe2.role == "Admin")
    db.close()
    check("Old password no longer works after reset", AuthService.login("jdoe", "secret123") is None)
    check("New password works after reset", AuthService.login("jdoe", "newpass456") is not None)

# --- 5. Self-lockout protection: admin can't deactivate themselves ---
controller._load_user_list()
admin_row = None
for i in range(window.userList.count()):
    if window.userList.item(i).text().startswith("admin"):
        admin_row = i
        break
if admin_row is not None:
    window.userList.setCurrentRow(admin_row)
    window.activeCheck.setChecked(False)
    controller.on_save()
    db = SessionLocal()
    still_active = db.query(User).filter_by(username="admin").first().active
    db.close()
    check("Admin can't deactivate their own account", still_active is True)

# --- 6. Last-SuperUser protection: can't demote the only SuperUser ---
if admin_row is not None:
    window.userList.setCurrentRow(admin_row)
    window.activeCheck.setChecked(True)
    window.roleCombo.setCurrentText("Operator")
    controller.on_save()
    db = SessionLocal()
    admin_role_after = db.query(User).filter_by(username="admin").first().role
    db.close()
    check("Can't demote the only active SuperUser", admin_role_after == "SuperUser")

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")

os.remove("test_user_editor.db")
