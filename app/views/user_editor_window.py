from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QComboBox, QGroupBox, QFormLayout, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt

from app.models import roles


class UserEditorWindow(QWidget):
    """SuperUser-only screen: pick a user on the left to edit them, or
    create a new one. Password fields are only required when creating a
    user or explicitly resetting a password - left blank, an edit keeps
    the existing password.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Barcode Placeholder App - User Management")
        self.resize(640, 420)

        root = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(QLabel("Users"))
        self.userList = QListWidget()
        left.addWidget(self.userList)
        self.newButton = QPushButton("New User")
        left.addWidget(self.newButton)
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMaximumWidth(260)

        right = QVBoxLayout()

        identity_box = QGroupBox("Account")
        form = QFormLayout()
        self.usernameInput = QLineEdit()
        self.fullnameInput = QLineEdit()
        self.roleCombo = QComboBox()
        self.roleCombo.addItems(list(roles.ALL_ROLES))
        self.activeCheck = QCheckBox("Active")
        self.activeCheck.setChecked(True)
        form.addRow("Username", self.usernameInput)
        form.addRow("Full name", self.fullnameInput)
        form.addRow("Role", self.roleCombo)
        form.addRow("", self.activeCheck)
        identity_box.setLayout(form)
        right.addWidget(identity_box)

        password_box = QGroupBox("Password")
        pform = QFormLayout()
        self.passwordInput = QLineEdit()
        self.passwordInput.setEchoMode(QLineEdit.Password)
        self.passwordConfirmInput = QLineEdit()
        self.passwordConfirmInput.setEchoMode(QLineEdit.Password)
        pform.addRow("New password", self.passwordInput)
        pform.addRow("Confirm", self.passwordConfirmInput)
        self.passwordHintLabel = QLabel("Required for a new user. Leave both blank when editing to keep the current password.")
        self.passwordHintLabel.setWordWrap(True)
        self.passwordHintLabel.setStyleSheet("color: #777; font-size: 11px;")
        pform.addRow(self.passwordHintLabel)
        password_box.setLayout(pform)
        right.addWidget(password_box)

        self.saveButton = QPushButton("Save")
        right.addWidget(self.saveButton)
        self.closeButton = QPushButton("Close")
        right.addWidget(self.closeButton)
        right.addStretch()

        right_widget = QWidget()
        right_widget.setLayout(right)

        root.addWidget(left_widget)
        root.addWidget(right_widget)
        self.setLayout(root)

    def show_error(self, message):
        QMessageBox.warning(self, "Error", message)

    def show_info(self, message):
        QMessageBox.information(self, "Info", message)

    def clear_form(self):
        self.usernameInput.clear()
        self.usernameInput.setEnabled(True)
        self.fullnameInput.clear()
        self.roleCombo.setCurrentIndex(self.roleCombo.findText(roles.OPERATOR))
        self.activeCheck.setChecked(True)
        self.passwordInput.clear()
        self.passwordConfirmInput.clear()

    def set_user_list(self, users):
        self.userList.clear()
        for u in users:
            status = "active" if u.active else "INACTIVE"
            item_text = f"{u.username}  [{u.role}, {status}]"
            self.userList.addItem(item_text)
            self.userList.item(self.userList.count() - 1).setData(Qt.UserRole, u.id)
