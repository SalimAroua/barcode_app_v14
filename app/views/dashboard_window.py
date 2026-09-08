from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QGroupBox, QMessageBox, QFrame, QSizePolicy, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PySide6.QtWidgets import QGridLayout
from PySide6.QtCore import Qt

from app.models import roles
from app.views.window_utils import enable_maximize, set_app_icon


class DashboardWindow(QWidget):
    """Landing screen after login. Lets any role start a scan session
    against an active receipt. Admin/SuperUser-only actions are shown
    conditionally based on the logged-in user's role.
    """

    def __init__(self, user):
        super().__init__()
        enable_maximize(self)
        set_app_icon(self)
        self.user = user
        self.setStyleSheet(
            "QWidget { color: #d7dde5; font-size: 12px; }"
            "QGroupBox { background: #272a2e; border: 1px solid #4b535d; "
            "border-radius: 4px; margin-top: 10px; padding: 12px; }"
            "QGroupBox::title { color: #e2e8f0; subcontrol-origin: margin; "
            "left: 12px; padding: 0 5px; font-size: 13px; font-weight: 600; }"
            "QLabel { color: #cbd3dc; font-size: 12px; }"
            "QLineEdit { min-height: 28px; padding: 3px 8px; background: #30343a; "
            "color: #f1f5f9; border: 1px solid #59636e; border-radius: 3px; "
            "font-size: 13px; }"
            "QLineEdit:focus { border: 1px solid #6fa8dc; background: #353b42; }"
            "QLineEdit:disabled { color: #7f8994; background: #272a2e; }"
            "QPushButton#startSessionButton { min-height: 34px; background: #356d99; "
            "color: #ffffff; border: 1px solid #5b9bd0; border-radius: 3px; "
            "font-size: 13px; font-weight: 600; }"
            "QPushButton#startSessionButton:hover { background: #4384b5; }"
            "QPushButton#startSessionButton:pressed { background: #2b5c83; }"
            "QTableWidget { background: #25282c; color: #dce3eb; "
            "gridline-color: #414850; alternate-background-color: #2d3238; "
            "font-size: 12px; }"
            "QHeaderView::section { background: #3a424b; color: #e5ebf2; "
            "padding: 5px; border: 0; font-weight: 600; }"
        )

        self.setWindowTitle("Barcode Placeholder App - Dashboard")
        self.resize(980, 620)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        command_bar = QFrame()
        command_bar.setObjectName("commandBar")
        command_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        command_bar.setMaximumHeight(40)
        command_bar.setStyleSheet(
            "QFrame#commandBar { background: #2b2d30; border: 1px solid #454a50; "
            "border-radius: 2px; }"
            "QPushButton { padding: 2px 10px; min-height: 22px; border: 1px solid #555b63; "
            "background: #3a3e43; color: #d7dbe0; border-radius: 2px; }"
            "QPushButton:hover:enabled { background: #46515d; border-color: #71879d; }"
            "QPushButton:pressed:enabled { background: #506070; }"
            "QPushButton:disabled { color: #777d84; background: #303337; }"
        )
        command_layout = QHBoxLayout(command_bar)
        command_layout.setContentsMargins(4, 3, 4, 3)
        command_layout.setSpacing(4)

        self.loginButton = QPushButton("Login")
        self.loginButton.setEnabled(False)
        self.loginButton.setToolTip("Current session")
        command_layout.addWidget(self.loginButton)

        self.manageReceiptsButton = QPushButton("Manage Receipt Definitions")
        self.exportButton = QPushButton("Export Scan History")
        self.printerSettingsButton = QPushButton("Zebra Printer Settings")
        self.manageUsersButton = QPushButton("Manage Users")
        for button in (
            self.manageReceiptsButton,
            self.exportButton,
            self.printerSettingsButton,
            self.manageUsersButton,
        ):
            button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            command_layout.addWidget(button)

        command_layout.addStretch()
        self.logoutButton = QPushButton("Log out")
        command_layout.addWidget(self.logoutButton)
        layout.addWidget(command_bar)

        identity_label = QLabel(f"Logged in as: {user.fullname} ({user.role})")
        identity_label.setAlignment(Qt.AlignLeft)
        identity_label.setStyleSheet("color: #4b5563; padding: 2px 4px;")
        layout.addWidget(identity_label)

        self.manageReceiptsButton.setEnabled(user.role in roles.CAN_MANAGE_RECEIPTS)
        self.exportButton.setEnabled(user.role in roles.CAN_MANAGE_RECEIPTS)
        self.printerSettingsButton.setEnabled(user.role in roles.CAN_MANAGE_RECEIPTS)
        self.manageUsersButton.setEnabled(user.role in roles.CAN_MANAGE_USERS)

        session_box = QGroupBox("Start a Scan Session")
        session_layout = QGridLayout()
        session_layout.setContentsMargins(14, 12, 14, 14)
        session_layout.setHorizontalSpacing(12)
        session_layout.setVerticalSpacing(8)

        receipt_label = QLabel("Receipt")
        session_layout.addWidget(receipt_label, 0, 0)
        self.receiptNameInput = QLineEdit()
        self.receiptNameInput.setPlaceholderText("Scan/type receipt name or barcode")
        session_layout.addWidget(self.receiptNameInput, 0, 1, 1, 3)

        self.operatorInputs = []
        self.operatorRows = []
        self.operatorLabels = []
        self.operatorCapacityLabel = QLabel("Select a receipt to configure operators")
        self.operatorCapacityLabel.setStyleSheet("color: #666; font-size: 11px;")
        session_layout.addWidget(self.operatorCapacityLabel, 1, 0, 1, 4)
        for operator_index in range(10):
            row = QHBoxLayout()
            row.setSpacing(6)
            operator_label = QLabel(f"Operator {operator_index + 1}")
            row.addWidget(operator_label)
            operator_input = QLineEdit()
            operator_input.setPlaceholderText("Employee ID or name")
            row.addWidget(operator_input)
            operator_row = 2 + operator_index // 2
            operator_column = (operator_index % 2) * 2
            session_layout.addLayout(row, operator_row, operator_column, 1, 2)
            self.operatorInputs.append(operator_input)
            self.operatorRows.append(row)
            self.operatorLabels.append(operator_label)
        self.operatorNumberInput = self.operatorInputs[0]

        field_row = 7
        session_layout.addWidget(QLabel("Line"), field_row, 0)
        self.lineNumberInput = QLineEdit()
        session_layout.addWidget(self.lineNumberInput, field_row, 1)

        session_layout.addWidget(QLabel("Plain Line #"), field_row, 2)
        self.plainLineNumberInput = QLineEdit()
        session_layout.addWidget(self.plainLineNumberInput, field_row, 3)

        session_layout.addWidget(QLabel("Target"), field_row + 1, 0)
        self.targetQuantityInput = QLineEdit()
        self.targetQuantityInput.setPlaceholderText("Optional")
        session_layout.addWidget(self.targetQuantityInput, field_row + 1, 1)

        session_layout.addWidget(QLabel("Batch"), field_row + 1, 2)
        self.batchLabelInput = QLineEdit()
        session_layout.addWidget(self.batchLabelInput, field_row + 1, 3)

        self.startSessionButton = QPushButton("Start Session")
        self.startSessionButton.setObjectName("startSessionButton")
        self.startSessionButton.setMinimumHeight(30)
        session_layout.addWidget(self.startSessionButton, field_row + 2, 0, 1, 4)
        for input_widget in (
            self.receiptNameInput, *self.operatorInputs, self.lineNumberInput,
            self.plainLineNumberInput, self.targetQuantityInput, self.batchLabelInput,
        ):
            input_widget.returnPressed.connect(self.startSessionButton.click)

        session_box.setLayout(session_layout)
        session_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        session_box.setMaximumWidth(1000)
        layout.addWidget(session_box, alignment=Qt.AlignTop | Qt.AlignHCenter)

        kpi_box = QGroupBox("Production KPIs")
        kpi_layout = QHBoxLayout()
        self.kpiLabels = {}
        for key, title in (
            ("yield", "First-pass yield"),
            ("nok_rate", "NOK rate"),
            ("takt", "Avg tack time"),
            ("parts_hour", "Parts / hour"),
            ("target", "Target progress"),
            ("eta", "Estimated completion"),
        ):
            label = QLabel(f"{title}: -")
            label.setAlignment(Qt.AlignCenter)
            label.setMinimumWidth(120)
            self.kpiLabels[key] = label
            kpi_layout.addWidget(label)
        kpi_box.setLayout(kpi_layout)
        layout.addWidget(kpi_box)

        followup_box = QGroupBox("Session Follow-up")
        followup_layout = QVBoxLayout()
        followup_header = QHBoxLayout()
        followup_header.addWidget(QLabel("All scan sessions"))
        followup_header.addStretch()
        self.refreshSessionsButton = QPushButton("Refresh")
        self.refreshSessionsButton.setMaximumWidth(100)
        followup_header.addWidget(self.refreshSessionsButton)
        followup_layout.addLayout(followup_header)
        self.sessionTable = QTableWidget(0, 10)
        self.sessionTable.setHorizontalHeaderLabels([
            "Session", "Receipt", "PN", "OK", "NOK", "Tested",
            "Cycle time", "Started", "Ended", "Status",
        ])
        self.sessionTable.setSelectionBehavior(QTableWidget.SelectRows)
        self.sessionTable.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sessionTable.setAlternatingRowColors(True)
        self.sessionTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.sessionTable.horizontalHeader().setStretchLastSection(True)
        self.sessionTable.setMinimumHeight(170)
        followup_layout.addWidget(self.sessionTable)
        followup_box.setLayout(followup_layout)
        followup_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(followup_box)
        layout.addStretch(1)

        self.setLayout(layout)
        self.set_operator_count(1)

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

    def set_operator_count(self, count):
        count = max(1, min(10, int(count or 1)))
        self.operatorCapacityLabel.setText(
            f"{count} operator field{'s' if count != 1 else ''} available for this receipt"
        )
        for index, row in enumerate(self.operatorRows):
            enabled = index < count
            self.operatorInputs[index].setEnabled(enabled)
            self.operatorLabels[index].setEnabled(enabled)
            self.operatorInputs[index].setVisible(enabled)
            self.operatorLabels[index].setVisible(enabled)
            if not enabled:
                self.operatorInputs[index].clear()

    def update_kpis(self, kpis):
        self.kpiLabels["yield"].setText(f"First-pass yield: {kpis['first_pass_yield']:.1f}%")
        self.kpiLabels["nok_rate"].setText(f"NOK rate: {kpis['nok_rate']:.1f}%")
        self.kpiLabels["takt"].setText(
            f"Avg tack time: {self._format_duration(kpis['average_takt_seconds'])}"
        )
        self.kpiLabels["parts_hour"].setText(f"Parts / hour: {kpis['parts_per_hour']:.1f}")
        self.kpiLabels["target"].setText(f"Target progress: {kpis['target_progress']}")
        self.kpiLabels["eta"].setText(f"Estimated completion: {kpis['eta']}")

    @staticmethod
    def _format_duration(seconds):
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
