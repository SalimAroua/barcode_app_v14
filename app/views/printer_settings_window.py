from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt


class PrinterSettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Zebra Printer Settings")
        self.resize(500, 300)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Configure the Zebra printer used for completed batch labels."))

        connection_box = QGroupBox("Connection")
        connection_box.setMaximumWidth(680)
        form = QFormLayout()
        self.modeCombo = QComboBox()
        self.modeCombo.addItem("Network printer (TCP)", "network")
        self.modeCombo.addItem("USB printer (Windows spooler)", "usb")
        self.hostInput = QLineEdit()
        self.portInput = QLineEdit()
        self.timeoutInput = QLineEdit()
        self.usbPrinterCombo = QComboBox()
        self.usbPrinterCombo.setEditable(True)
        self.refreshUsbButton = QPushButton("Refresh USB printers")
        form.addRow("Printer mode", self.modeCombo)
        form.addRow("Network host", self.hostInput)
        form.addRow("TCP port", self.portInput)
        form.addRow("Timeout (seconds)", self.timeoutInput)
        form.addRow("USB printer", self.usbPrinterCombo)
        form.addRow("", self.refreshUsbButton)
        connection_box.setLayout(form)
        layout.addWidget(connection_box, alignment=Qt.AlignHCenter)

        self.statusLabel = QLabel("")
        self.statusLabel.setMaximumWidth(680)
        layout.addWidget(self.statusLabel)
        self.testButton = QPushButton("Send Test Label")
        self.saveButton = QPushButton("Save")
        self.closeButton = QPushButton("Close")
        for button in (self.testButton, self.saveButton, self.closeButton):
            button.setMaximumWidth(680)
            layout.addWidget(button, alignment=Qt.AlignHCenter)
        self.setLayout(layout)

    def show_error(self, message):
        QMessageBox.warning(self, "Printer settings", message)

    def show_info(self, message):
        QMessageBox.information(self, "Printer settings", message)
