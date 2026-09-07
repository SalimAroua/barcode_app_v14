from app.services import printer_service
from app.domain.exceptions import PrinterError


class PrinterSettingsController:
    def __init__(self, view):
        self.view = view
        self.view.modeCombo.currentIndexChanged.connect(self._update_mode)
        self.view.refreshUsbButton.clicked.connect(self.refresh_usb_printers)
        self.view.testButton.clicked.connect(self.on_test_print)
        self.view.saveButton.clicked.connect(self.on_save)
        self.view.closeButton.clicked.connect(self.view.close)
        self._load()
        self.refresh_usb_printers()
        self._update_mode()

    def _load(self):
        settings = printer_service.load_settings()
        index = self.view.modeCombo.findData(settings["mode"])
        self.view.modeCombo.setCurrentIndex(max(index, 0))
        self.view.hostInput.setText(str(settings["host"]))
        self.view.portInput.setText(str(settings["port"]))
        self.view.timeoutInput.setText(str(settings["timeout"]))
        self.view.usbPrinterCombo.setEditText(settings["usb_printer_name"])

    def refresh_usb_printers(self):
        current = self.view.usbPrinterCombo.currentText()
        self.view.usbPrinterCombo.clear()
        self.view.usbPrinterCombo.addItems(printer_service.list_usb_printers())
        self.view.usbPrinterCombo.setEditText(current)
        if not self.view.usbPrinterCombo.count():
            self.view.usbPrinterCombo.setToolTip(
                "USB discovery requires pywin32 and a Windows-installed printer."
            )

    def _update_mode(self, *_args):
        network = self.view.modeCombo.currentData() == "network"
        self.view.hostInput.setEnabled(network)
        self.view.portInput.setEnabled(network)
        self.view.timeoutInput.setEnabled(network)
        self.view.usbPrinterCombo.setEnabled(not network)
        self.view.refreshUsbButton.setEnabled(not network)

    def _settings_from_form(self):
        try:
            port = int(self.view.portInput.text().strip())
            timeout = float(self.view.timeoutInput.text().strip())
        except ValueError as exc:
            raise ValueError("TCP port must be a whole number and timeout must be numeric.") from exc
        if not 1 <= port <= 65535:
            raise ValueError("TCP port must be between 1 and 65535.")
        if timeout <= 0:
            raise ValueError("Timeout must be greater than zero.")
        return {
            "mode": self.view.modeCombo.currentData(),
            "host": self.view.hostInput.text().strip(),
            "port": port,
            "timeout": timeout,
            "usb_printer_name": self.view.usbPrinterCombo.currentText().strip(),
        }

    def on_save(self):
        try:
            printer_service.save_settings(self._settings_from_form())
        except (OSError, ValueError) as exc:
            self.view.show_error(str(exc))
            return
        self.view.statusLabel.setText("Printer settings saved.")

    def on_test_print(self):
        try:
            settings = self._settings_from_form()
            printer_service.send_zpl(
                b"^XA^CF0,36^FO40,40^FDBarcode app Zebra test^FS^XZ\n",
                settings,
            )
        except (OSError, RuntimeError, ValueError, PrinterError) as exc:
            self.view.show_error(f"Test print failed: {exc}")
            return
        self.view.statusLabel.setText("Test label sent successfully.")
