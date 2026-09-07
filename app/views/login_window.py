from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout
)


class LoginWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Barcode Placeholder App")
        self.resize(350, 220)

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Username"))

        self.username = QLineEdit()

        layout.addWidget(self.username)

        layout.addWidget(QLabel("Password"))

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)

        layout.addWidget(self.password)

        self.loginButton = QPushButton("Login")

        layout.addWidget(self.loginButton)

        self.setLayout(layout)