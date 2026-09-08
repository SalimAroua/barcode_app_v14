from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QComboBox, QGroupBox, QFormLayout, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt

from app.models import roles
from app.views.window_utils import enable_maximize, set_app_icon


class UserEditorWindow(QWidget):
    """SuperUser-only screen: pick a user on the left to edit them, or
    create a new one. Password fields are only required when creating a
    user or explicitly resetting a password - left blank, an edit keeps
    the existing password.
    """

    def __init__(self):
        super().__init__()
        enable_maximize(self)
        set_app_icon(self)
        self.setWindowTitle("Barcode Placeholder App - User Management")
        self.resize(640, 420)

        root = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(QLabel("Users"))
        self.userList = QListWidget()
        left.addWidget(self.userList)
        self.newButton = QPushButton("New User")
        left.addWidget(self.newButton)
        self.importCsvButton = QPushButton("Import CSV...")
        left.addWidget(self.importCsvButton)
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMinimumWidth(260)
        left_widget.setMaximumWidth(380)

        right = QVBoxLayout()

        identity_box = QGroupBox("Account")
        form = QFormLayout()
        self.usernameInput = QLineEdit()
        self.fullnameInput = QLineEdit()
        self.employeeIdInput = QLineEdit()
        self.teamLeaderInput = QLineEdit()
        self.shiftLeaderInput = QLineEdit()
        self.roleCombo = QComboBox()
        self.roleCombo.addItems(list(roles.ALL_ROLES))
        self.activeCheck = QCheckBox("Active")
        self.activeCheck.setChecked(True)
        form.addRow("Username", self.usernameInput)
        form.addRow("Full name", self.fullnameInput)
        form.addRow("Employee ID", self.employeeIdInput)
        form.addRow("Team leader", self.teamLeaderInput)
        form.addRow("Shift leader", self.shiftLeaderInput)
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
        right_widget.setMaximumWidth(620)

        root.addWidget(left_widget)
        root.addWidget(right_widget)
        root.setAlignment(Qt.AlignHCenter)
        self.setLayout(root)

    def show_error(self, message):
        QMessageBox.warning(self, "Error", message)

    def show_info(self, message):
        QMessageBox.information(self, "Info", message)

    def clear_form(self):
        self.usernameInput.clear()
        self.usernameInput.setEnabled(True)
        self.fullnameInput.clear()
        self.employeeIdInput.clear()
        self.teamLeaderInput.clear()
        self.shiftLeaderInput.clear()
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
