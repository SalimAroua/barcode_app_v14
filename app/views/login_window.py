from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QGroupBox,
)
from PySide6.QtCore import Qt

from app.views.window_utils import enable_maximize, set_app_icon


class LoginWindow(QWidget):

    def __init__(self):
        super().__init__()
        enable_maximize(self)
        set_app_icon(self)

        self.setWindowTitle("Barcode Placeholder App")
        self.resize(350, 220)

        root = QVBoxLayout()
        root.setContentsMargins(24, 24, 24, 24)

        card = QGroupBox("Barcode Placeholder App")
        card.setMaximumWidth(440)
        layout = QVBoxLayout()
        layout.setContentsMargins(28, 24, 28, 28)

        subtitle = QLabel("Sign in to continue")
        subtitle.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(subtitle)
        layout.addSpacing(10)

        layout.addWidget(QLabel("Username"))

        self.username = QLineEdit()

        layout.addWidget(self.username)

        layout.addWidget(QLabel("Password"))

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)

        layout.addWidget(self.password)

        self.loginButton = QPushButton("Login")
        self.loginButton.setMinimumHeight(34)
        layout.addWidget(self.loginButton)

        card.setLayout(layout)
        root.addWidget(card, alignment=Qt.AlignHCenter | Qt.AlignVCenter)
        self.setLayout(root)