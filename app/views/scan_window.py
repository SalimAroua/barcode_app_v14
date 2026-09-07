from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt


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
        self.scanInput.setMaximumWidth(900)
        layout.addWidget(self.scanInput, alignment=Qt.AlignHCenter)

        self.resultLabel = QLabel("")
        layout.addWidget(self.resultLabel)

        self.targetStatusLabel = QLabel(self._target_status_text(session, 0))
        self.targetStatusLabel.setMaximumWidth(900)
        layout.addWidget(self.targetStatusLabel, alignment=Qt.AlignHCenter)

        self.labelStatusLabel = QLabel("Label status: not printed")
        self.labelStatusLabel.setMaximumWidth(1100)
        layout.addWidget(self.labelStatusLabel, alignment=Qt.AlignHCenter)

        self.logList = QListWidget()
        self.logList.setMaximumWidth(1100)
        layout.addWidget(self.logList, alignment=Qt.AlignHCenter)

        self.endSessionButton = QPushButton("End Session")
        layout.addWidget(self.endSessionButton)

        self.reprintLabelButton = QPushButton("Reprint Label")
        self.reprintLabelButton.setVisible(False)
        layout.addWidget(self.reprintLabelButton)

        self.setLayout(layout)
        self.scanInput.setFocus()

    @staticmethod
    def _target_status_text(session, successful_count):
        if session.target_quantity is None:
            return f"Successful scans: {successful_count}"
        return f"Target: {successful_count} / {session.target_quantity}"

    def update_session_status(self, session, successful_count):
        self.targetStatusLabel.setText(self._target_status_text(session, successful_count))
        if session.printed_label_path:
            self.labelStatusLabel.setText(f"Target reached / label printed: {session.printed_label_path}")
            self.labelStatusLabel.setStyleSheet("color: green; font-weight: bold;")
            self.stop_scanning("Target reached. Scanning stopped.", show_message=False)
        else:
            self.labelStatusLabel.setText("Label status: not printed")

    def set_reprint_available(self, available):
        self.reprintLabelButton.setVisible(available)

    def show_printer_error(self, message):
        self.labelStatusLabel.setText(f"Label not printed: {message}")
        self.labelStatusLabel.setStyleSheet("color: darkred; font-weight: bold;")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Zebra printer error", message)

    def stop_scanning(self, message, show_message=True):
        self.scanInput.clear()
        self.scanInput.setEnabled(False)
        self.scanInput.setPlaceholderText("Scanning stopped")
        self.endSessionButton.setEnabled(True)
        if show_message:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Scanning stopped", message)

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
