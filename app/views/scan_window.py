from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem
)
from PySide6.QtGui import QColor


class ScanWindow(QWidget):
    """Operator scanning screen: one text field to receive barcode input
    (from a real scanner acting as a keyboard, or typed manually for
    testing), an Enter-to-submit flow, and a running log of results.
    """

    def __init__(self, session, receipt_name):
        super().__init__()
        self.session = session

        self.setWindowTitle("Barcode Placeholder App - Scanning")
        self.resize(560, 460)

        layout = QVBoxLayout()

        header = QHBoxLayout()
        header.addWidget(QLabel(f"Receipt: {receipt_name}"))
        header.addWidget(QLabel(f"  |  Line: {session.line_number}"))
        header.addWidget(QLabel(f"  |  Operator: {session.operator_number}"))
        layout.addLayout(header)

        layout.addWidget(QLabel("Scan or type a barcode value, then press Enter:"))

        self.scanInput = QLineEdit()
        self.scanInput.setPlaceholderText("Waiting for scan...")
        layout.addWidget(self.scanInput)

        self.resultLabel = QLabel("")
        layout.addWidget(self.resultLabel)

        self.logList = QListWidget()
        layout.addWidget(self.logList)

        self.endSessionButton = QPushButton("End Session")
        layout.addWidget(self.endSessionButton)

        self.setLayout(layout)
        self.scanInput.setFocus()

    def add_log_entry(self, scanned_value, ok, reason=None, unit_info=""):
        text = f"{'✓ OK' if ok else '✗ FAIL'}  {scanned_value}"
        if not ok and reason:
            text += f"   [{reason}]"
        if unit_info:
            text += f"   {unit_info}"
        item = QListWidgetItem(text)
        item.setForeground(QColor("darkgreen") if ok else QColor("darkred"))
        self.logList.insertItem(0, item)

    def show_result(self, ok, reason=None):
        if ok:
            self.resultLabel.setText("PASS")
            self.resultLabel.setStyleSheet("color: green; font-weight: bold; font-size: 16px;")
        else:
            self.resultLabel.setText(f"FAIL ({reason})")
            self.resultLabel.setStyleSheet("color: red; font-weight: bold; font-size: 16px;")

    def clear_input(self):
        self.scanInput.clear()
        self.scanInput.setFocus()
