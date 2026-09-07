from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt

from app.models import roles


class DashboardWindow(QWidget):
    """Landing screen after login. Lets any role start a scan session
    against an active receipt. Admin/SuperUser-only actions are shown
    conditionally based on the logged-in user's role.
    """

    def __init__(self, user):
        super().__init__()
        self.user = user

        self.setWindowTitle("Barcode Placeholder App - Dashboard")
        self.resize(420, 380)

        layout = QVBoxLayout()

        identity_label = QLabel(f"Logged in as: {user.fullname} ({user.role})")
        identity_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(identity_label)

        if user.role in roles.CAN_MANAGE_RECEIPTS or user.role in roles.CAN_MANAGE_USERS:
            admin_box = QGroupBox("Admin")
            admin_layout = QVBoxLayout()
            if user.role in roles.CAN_MANAGE_RECEIPTS:
                self.manageReceiptsButton = QPushButton("Manage Receipt Definitions")
                admin_layout.addWidget(self.manageReceiptsButton)
                self.exportButton = QPushButton("Export Scan History")
                admin_layout.addWidget(self.exportButton)
                self.printerSettingsButton = QPushButton("Zebra Printer Settings")
                admin_layout.addWidget(self.printerSettingsButton)
            if user.role in roles.CAN_MANAGE_USERS:
                self.manageUsersButton = QPushButton("Manage Users")
                admin_layout.addWidget(self.manageUsersButton)
            admin_box.setLayout(admin_layout)
            admin_box.setMaximumWidth(720)
            layout.addWidget(admin_box, alignment=Qt.AlignHCenter)

        session_box = QGroupBox("Start a Scan Session")
        session_layout = QVBoxLayout()

        session_layout.addWidget(QLabel("Receipt"))
        self.receiptNameInput = QLineEdit()
        self.receiptNameInput.setPlaceholderText("Scan/type receipt name or barcode")
        session_layout.addWidget(self.receiptNameInput)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Operator #"))
        self.operatorNumberInput = QLineEdit()
        row1.addWidget(self.operatorNumberInput)
        session_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Line"))
        self.lineNumberInput = QLineEdit()
        row2.addWidget(self.lineNumberInput)
        session_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Plain Line #"))
        self.plainLineNumberInput = QLineEdit()
        row3.addWidget(self.plainLineNumberInput)
        session_layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Operators"))
        self.operatorsInput = QLineEdit()
        row4.addWidget(self.operatorsInput)
        session_layout.addLayout(row4)

        row5 = QHBoxLayout()
        row5.addWidget(QLabel("Target"))
        self.targetQuantityInput = QLineEdit()
        self.targetQuantityInput.setPlaceholderText("Optional")
        row5.addWidget(self.targetQuantityInput)
        session_layout.addLayout(row5)

        row6 = QHBoxLayout()
        row6.addWidget(QLabel("Batch"))
        self.batchLabelInput = QLineEdit()
        row6.addWidget(self.batchLabelInput)
        session_layout.addLayout(row6)

        self.startSessionButton = QPushButton("Start Session")
        session_layout.addWidget(self.startSessionButton)

        session_box.setLayout(session_layout)
        session_box.setMaximumWidth(720)
        layout.addWidget(session_box, alignment=Qt.AlignHCenter)

        self.logoutButton = QPushButton("Log out")
        self.logoutButton.setMaximumWidth(720)
        layout.addWidget(self.logoutButton, alignment=Qt.AlignHCenter)

        self.setLayout(layout)

    def show_error(self, message):
        QMessageBox.warning(self, "Error", message)

    def show_info(self, message):
        QMessageBox.information(self, "Info", message)

    def set_batch_auto_generated(self, auto: bool):
        """Locks the Batch field and shows a hint when the selected
        receipt auto-generates its own batch number; unlocks it otherwise."""
        self.batchLabelInput.setEnabled(not auto)
        if auto:
            self.batchLabelInput.clear()
            self.batchLabelInput.setPlaceholderText("(auto-generated at session start)")
        else:
            self.batchLabelInput.setPlaceholderText("")
