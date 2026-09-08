from PySide6.QtWidgets import QMessageBox

from app.services.auth_service import AuthService
from app.views.dashboard_window import DashboardWindow
from app.controllers.dashboard_controller import DashboardController


class LoginController:

    def __init__(self, view):

        self.view = view
        self._dashboard_window = None  # keep a reference so it isn't garbage-collected
        self._dashboard_controller = None

        self.view.loginButton.clicked.connect(self.login)
        self.view.username.returnPressed.connect(self.login)
        self.view.password.returnPressed.connect(self.login)

    def login(self):

        username = self.view.username.text()
        password = self.view.password.text()

        user = AuthService.login(username, password)

        if user is None:

            QMessageBox.warning(
                self.view,
                "Error",
                "Invalid username or password."
            )
            return

        self._dashboard_window = DashboardWindow(user)
        self._dashboard_controller = DashboardController(self._dashboard_window, user)
        self._dashboard_window.show()
        self.view.close()
