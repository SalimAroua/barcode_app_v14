import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

import app.models

from app.database.session import SessionLocal

from migrations_runner import run_migrations_to_head
from app.services.auth_service import AuthService
from app.services import receipt_def_service

from app.views.login_window import LoginWindow
from app.controllers.login_controller import LoginController
from app.views.window_utils import app_resource_path


run_migrations_to_head()

AuthService.create_superuser()

_db = SessionLocal()
receipt_def_service.seed_demo_receipt_if_missing(_db)
_db.close()

app = QApplication(sys.argv)
app.setWindowIcon(QIcon(app_resource_path("assets/sa_logo_barcode.png")))

window = LoginWindow()

# IMPORTANT: keep a reference to the controller. Without this, Python can
# garbage-collect it right after construction, which silently breaks the
# button's click handling (clicking Login then does nothing at all).
login_controller = LoginController(window)

window.show()

sys.exit(app.exec())