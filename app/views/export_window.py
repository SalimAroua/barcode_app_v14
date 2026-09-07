from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QComboBox, QGroupBox, QFormLayout, QMessageBox,
    QDateTimeEdit, QStackedWidget
)
from PySide6.QtCore import Qt, QDateTime


class ExportWindow(QWidget):
    """Admin/SuperUser screen: export scan history to CSV or XLSX, either
    for one ScanSession or for a ReceiptDefinition within a date range.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Barcode Placeholder App - Export Scan History")
        self.resize(640, 480)

        root = QVBoxLayout()

        mode_box = QGroupBox("Export by")
        mode_layout = QHBoxLayout()
        self.modeCombo = QComboBox()
        self.modeCombo.addItems(["Session", "Receipt + Date Range"])
        mode_layout.addWidget(self.modeCombo)
        mode_box.setLayout(mode_layout)
        root.addWidget(mode_box)

        self.stack = QStackedWidget()

        # --- Page 0: by session ---
        session_page = QWidget()
        session_layout = QVBoxLayout()
        session_layout.addWidget(QLabel("Pick a scan session:"))
        self.sessionList = QListWidget()
        session_layout.addWidget(self.sessionList)
        session_page.setLayout(session_layout)
        self.stack.addWidget(session_page)

        # --- Page 1: by receipt + date range ---
        receipt_page = QWidget()
        receipt_layout = QVBoxLayout()
        form = QFormLayout()
        self.receiptCombo = QComboBox()
        form.addRow("Receipt", self.receiptCombo)
        self.startDateTime = QDateTimeEdit()
        self.startDateTime.setCalendarPopup(True)
        self.startDateTime.setDateTime(QDateTime.currentDateTime().addDays(-7))
        form.addRow("From", self.startDateTime)
        self.endDateTime = QDateTimeEdit()
        self.endDateTime.setCalendarPopup(True)
        self.endDateTime.setDateTime(QDateTime.currentDateTime())
        form.addRow("To", self.endDateTime)
        receipt_layout.addLayout(form)
        receipt_layout.addStretch()
        receipt_page.setLayout(receipt_layout)
        self.stack.addWidget(receipt_page)

        root.addWidget(self.stack)

        format_box = QGroupBox("Format")
        format_layout = QHBoxLayout()
        self.formatCombo = QComboBox()
        self.formatCombo.addItems(["CSV", "XLSX"])
        format_layout.addWidget(self.formatCombo)
        format_box.setLayout(format_layout)
        root.addWidget(format_box)

        buttons = QHBoxLayout()
        self.exportButton = QPushButton("Export...")
        buttons.addWidget(self.exportButton)
        self.closeButton = QPushButton("Close")
        buttons.addWidget(self.closeButton)
        root.addLayout(buttons)

        self.setLayout(root)

        self.modeCombo.currentIndexChanged.connect(self.stack.setCurrentIndex)

    def show_error(self, message):
        QMessageBox.warning(self, "Error", message)

    def show_info(self, message):
        QMessageBox.information(self, "Info", message)

    def set_session_list(self, sessions_with_labels):
        """sessions_with_labels: list of (session_id, label_text)."""
        self.sessionList.clear()
        for session_id, label in sessions_with_labels:
            self.sessionList.addItem(label)
            self.sessionList.item(self.sessionList.count() - 1).setData(Qt.UserRole, session_id)

    def set_receipt_list(self, receipts_with_labels):
        """receipts_with_labels: list of (receipt_id, label_text)."""
        self.receiptCombo.clear()
        for receipt_id, label in receipts_with_labels:
            self.receiptCombo.addItem(label, userData=receipt_id)
