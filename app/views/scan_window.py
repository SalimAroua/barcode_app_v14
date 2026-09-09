from datetime import datetime, timezone

from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QGroupBox
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer

from app.views.window_utils import enable_maximize, set_app_icon


class ScanWindow(QWidget):
    """Operator scanning screen with primary/companion inputs when required,
    Enter-to-submit scanning, session metrics, and a running result log.
    """

    def __init__(self, session, receipt_name, companion_enabled=False):
        super().__init__()
        enable_maximize(self)
        set_app_icon(self)
        self.session = session

        self.setWindowTitle("Barcode Placeholder App - Scanning")
        self.resize(560, 460)

        layout = QVBoxLayout()

        header = QHBoxLayout()
        header.addWidget(QLabel(f"Receipt: {receipt_name}"))
        header.addWidget(QLabel(f"  |  Line: {session.line_number}"))
        header.addWidget(QLabel(f"  |  Operator: {session.operator_number}"))
        layout.addLayout(header)

        self.primaryScanLabel = QLabel("Primary label: scan or type a barcode")
        layout.addWidget(self.primaryScanLabel)

        self.scanInput = QLineEdit()
        self.scanInput.setPlaceholderText("Waiting for scan...")
        self.scanInput.setMaximumWidth(900)
        layout.addWidget(self.scanInput, alignment=Qt.AlignHCenter)

        self.companionScanLabel = QLabel("Companion label: scan or type a barcode")
        self.companionScanLabel.setVisible(False)
        layout.addWidget(self.companionScanLabel)
        self.companionScanInput = QLineEdit()
        self.companionScanInput.setPlaceholderText("Waiting for companion label scan...")
        self.companionScanInput.setMaximumWidth(900)
        self.companionScanInput.setVisible(False)
        layout.addWidget(self.companionScanInput, alignment=Qt.AlignHCenter)

        self.resultLabel = QLabel("")
        layout.addWidget(self.resultLabel)

        self.targetStatusLabel = QLabel(self._target_status_text(session, 0))
        self.targetStatusLabel.setMaximumWidth(900)
        layout.addWidget(self.targetStatusLabel, alignment=Qt.AlignHCenter)

        self.labelStatusLabel = QLabel("Label status: not printed")
        self.labelStatusLabel.setMaximumWidth(1100)
        layout.addWidget(self.labelStatusLabel, alignment=Qt.AlignHCenter)

        metrics_box = QGroupBox("Session metrics")
        metrics_layout = QHBoxLayout()
        self.receiptMetricLabel = QLabel("Receipt: -")
        self.partMetricLabel = QLabel("PN: -")
        self.okMetricLabel = QLabel("OK: 0")
        self.nokMetricLabel = QLabel("NOK: 0")
        self.testedMetricLabel = QLabel("Tested: 0")
        self.cycleMetricLabel = QLabel("Cycle time: 00:00:00")
        for label in (
            self.receiptMetricLabel, self.partMetricLabel, self.okMetricLabel,
            self.nokMetricLabel, self.testedMetricLabel, self.cycleMetricLabel,
        ):
            metrics_layout.addWidget(label)
        metrics_box.setLayout(metrics_layout)
        layout.addWidget(metrics_box)

        self.logList = QListWidget()
        self.logList.setMaximumWidth(1100)
        layout.addWidget(self.logList, alignment=Qt.AlignHCenter)

        self.endSessionButton = QPushButton("End Session")
        layout.addWidget(self.endSessionButton)

        self.reprintLabelButton = QPushButton("Reprint Label")
        self.reprintLabelButton.setVisible(False)
        layout.addWidget(self.reprintLabelButton)

        self.previewLabelButton = QPushButton("Preview ZPL Label")
        layout.addWidget(self.previewLabelButton)

        self.setLayout(layout)
        self.configure_companion_mode(companion_enabled)
        self.scanInput.setFocus()
        self._metrics_session = session
        self._metrics_timer = QTimer(self)
        self._metrics_timer.timeout.connect(self._refresh_cycle_time)
        self._metrics_timer.start(1000)

    @staticmethod
    def _target_status_text(session, successful_count):
        if session.target_quantity is None:
            return f"Successful scans: {successful_count}"
        return f"Target: {successful_count} / {session.target_quantity}"

    def update_session_status(self, session, successful_count):
        self._metrics_session = session
        self.targetStatusLabel.setText(self._target_status_text(session, successful_count))
        if session.printed_label_path:
            self.labelStatusLabel.setText(f"Target reached / label printed: {session.printed_label_path}")
            self.labelStatusLabel.setStyleSheet("color: green; font-weight: bold;")
            self.stop_scanning("Target reached. Scanning stopped.", show_message=False)
            self._metrics_timer.stop()
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

    def update_metrics(self, metrics):
        self.receiptMetricLabel.setText(f"Receipt: {metrics['receipt_name'] or '-'}")
        self.partMetricLabel.setText(f"PN: {metrics['part_number'] or '-'}")
        self.okMetricLabel.setText(f"OK: {metrics['ok_count']}")
        self.nokMetricLabel.setText(f"NOK: {metrics['nok_count']}")
        self.testedMetricLabel.setText(f"Tested: {metrics['tested_count']}")
        self._set_cycle_time(metrics["cycle_seconds"])

    def _refresh_cycle_time(self):
        session = self._metrics_session
        if session is None or session.started_at is None:
            return
        end_time = session.ended_at if not session.is_active and session.ended_at else datetime.now(timezone.utc)
        started_at = session.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        self._set_cycle_time(max(0, int((end_time - started_at).total_seconds())))

    def _set_cycle_time(self, seconds):
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.cycleMetricLabel.setText(f"Cycle time: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def configure_companion_mode(self, enabled):
        enabled = bool(enabled)
        self.companionScanLabel.setVisible(enabled)
        self.companionScanInput.setVisible(enabled)
        self.companionScanLabel.setEnabled(enabled)
        self.companionScanInput.setEnabled(enabled)
        if not enabled:
            self.companionScanInput.clear()

    def focus_companion_input(self):
        self.companionScanInput.clear()
        self.companionScanInput.setFocus()

    def focus_primary_input(self):
        self.scanInput.clear()
        self.scanInput.setFocus()
