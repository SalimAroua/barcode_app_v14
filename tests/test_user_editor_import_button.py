"""GUI smoke test for the User Management CSV import button."""
import csv
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DATABASE_URL"] = "sqlite:///test_user_editor_import.db"
if os.path.exists("test_user_editor_import.db"):
    os.remove("test_user_editor_import.db")

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)

import app.models  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.views.user_editor_window import UserEditorWindow  # noqa: E402
from app.controllers.user_editor_controller import UserEditorController  # noqa: E402


Base.metadata.create_all(engine)
AuthService.create_superuser()

with open("button_user_import_test.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["username", "fullname", "password", "role", "active"])
    writer.writeheader()
    writer.writerow({
        "username": "BUTTON_USER_IMPORT",
        "fullname": "Button Import User",
        "password": "secret123",
        "role": "Operator",
        "active": "true",
    })

QFileDialog.getOpenFileName = staticmethod(
    lambda *a, **k: ("button_user_import_test.csv", "CSV files (*.csv)")
)

qt_app = QApplication([])
db = SessionLocal()
acting_user = db.query(User).filter_by(username="admin").first()
before_count = db.query(User).count()
db.close()

window = UserEditorWindow()
controller = UserEditorController(window, acting_user)
window.importCsvButton.click()

db = SessionLocal()
imported = db.query(User).filter_by(username="BUTTON_USER_IMPORT").first()
after_count = db.query(User).count()
db.close()

assert after_count == before_count + 1
assert imported is not None
assert imported.fullname == "Button Import User"
assert any(
    window.userList.item(i).text().startswith("BUTTON_USER_IMPORT")
    for i in range(window.userList.count())
)

engine.dispose()
os.remove("button_user_import_test.csv")
os.remove("test_user_editor_import.db")
print("User editor CSV import button test passed")