from PySide6.QtWidgets import QMessageBox, QTableWidgetItem
from PySide6.QtCore import Qt, QTimer

from app.database.session import SessionLocal
from app.services import receipt_def_service, scan_service
from app.views.scan_window import ScanWindow
from app.controllers.scan_controller import ScanController
from app.views.receipt_editor_window import ReceiptEditorWindow
from app.controllers.receipt_editor_controller import ReceiptEditorController
from app.views.user_editor_window import UserEditorWindow
from app.controllers.user_editor_controller import UserEditorController
from app.views.export_window import ExportWindow
from app.controllers.export_controller import ExportController
from app.views.printer_settings_window import PrinterSettingsWindow
from app.controllers.printer_settings_controller import PrinterSettingsController


class DashboardController:
    def __init__(self, view, user):
        self.view = view
        self.user = user
        self._scan_window = None  # keep a reference so it isn't garbage-collected
        self._scan_controller = None
        self._receipt_editor_window = None
        self._receipt_editor_controller = None
        self._user_editor_window = None
        self._user_editor_controller = None
        self._export_window = None
        self._export_controller = None
        self._printer_settings_window = None
        self._printer_settings_controller = None
        self._followup_timer = QTimer(view)
        self._followup_timer.setInterval(2000)
        self._followup_timer.timeout.connect(self.refresh_session_followup)
        self._followup_timer.start()

        self._load_receipts()
        self.view.refreshSessionsButton.clicked.connect(self.refresh_session_followup)
        self.refresh_session_followup()
        self.view.receiptNameInput.textChanged.connect(self.on_receipt_selection_changed)

        self.view.startSessionButton.clicked.connect(self.on_start_session)
        self.view.logoutButton.clicked.connect(self.view.close)

        if hasattr(self.view, "manageReceiptsButton"):
            self.view.manageReceiptsButton.clicked.connect(self.on_manage_receipts)
        if hasattr(self.view, "manageUsersButton"):
            self.view.manageUsersButton.clicked.connect(self.on_manage_users)
        if hasattr(self.view, "exportButton"):
            self.view.exportButton.clicked.connect(self.on_export)
        if hasattr(self.view, "printerSettingsButton"):
            self.view.printerSettingsButton.clicked.connect(self.on_printer_settings)

    def on_not_implemented(self):
        self.view.show_info("This screen isn't built yet - coming soon.")

    def on_export(self):
        self._export_window = ExportWindow()
        self._export_controller = ExportController(self._export_window)
        self._export_window.setAttribute(Qt.WA_DeleteOnClose, True)
        self._export_window.show()

    def on_printer_settings(self):
        self._printer_settings_window = PrinterSettingsWindow()
        self._printer_settings_controller = PrinterSettingsController(self._printer_settings_window)
        self._printer_settings_window.setAttribute(Qt.WA_DeleteOnClose, True)
        self._printer_settings_window.show()

    def on_manage_receipts(self):
        self._receipt_editor_window = ReceiptEditorWindow()
        self._receipt_editor_controller = ReceiptEditorController(self._receipt_editor_window, self.user)
        self._receipt_editor_window.setAttribute(Qt.WA_DeleteOnClose, True)
        self._receipt_editor_window.destroyed.connect(lambda: self._load_receipts())
        self._receipt_editor_window.show()

    def on_manage_users(self):
        self._user_editor_window = UserEditorWindow()
        self._user_editor_controller = UserEditorController(self._user_editor_window, self.user)
        self._user_editor_window.setAttribute(Qt.WA_DeleteOnClose, True)
        self._user_editor_window.show()

    def refresh_session_followup(self):
        db = SessionLocal()
        try:
            rows = scan_service.list_scan_session_metrics(db)
            kpis = scan_service.get_dashboard_kpis(db)
        finally:
            db.close()

        try:
            self.view.update_kpis(kpis)
            self.view.sessionTable.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                values = [
                    row["session_id"], row["receipt_name"], row["part_number"],
                    row["ok_count"], row["nok_count"], row["tested_count"],
                    self._format_duration(row["cycle_seconds"]),
                    self._format_datetime(row["started_at"]),
                    self._format_datetime(row["ended_at"]),
                    "Active" if row["is_active"] else "Completed",
                ]
                for column, value in enumerate(values):
                    self.view.sessionTable.setItem(row_index, column, QTableWidgetItem(str(value)))
        except RuntimeError:
            # The dashboard may be closing after the scan window emits destroyed.
            return

    @staticmethod
    def _format_duration(seconds):
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _format_datetime(value):
        return value.astimezone().strftime("%Y-%m-%d %H:%M:%S") if value else "-"

    def _load_receipts(self):
        db = SessionLocal()
        try:
            receipts = receipt_def_service.list_active_receipts(db)
            self._receipt_auto_batch = {r.id: bool(r.auto_generate_batch_number) for r in receipts}
        finally:
            db.close()
        self.on_receipt_selection_changed()

    def on_receipt_selection_changed(self, *_args):
        receipt_name = self.view.receiptNameInput.text().strip()
        if not receipt_name:
            self.view.set_batch_auto_generated(False)
            self.view.set_operator_count(1)
            return

        db = SessionLocal()
        try:
            receipt = receipt_def_service.get_receipt_by_name(db, receipt_name)
            auto = bool(receipt and receipt.auto_generate_batch_number)
            operator_count = receipt.operator_count if receipt else 1
        finally:
            db.close()
        self.view.set_batch_auto_generated(auto)
        self.view.set_operator_count(operator_count)

    def on_start_session(self):
        receipt_name = self.view.receiptNameInput.text().strip()
        if not receipt_name:
            self.view.show_error("Receipt name is required to start a session.")
            return

        operator_values = [field.text().strip() for field in self.view.operatorInputs]
        operator_number = operator_values[0]
        line_number = self.view.lineNumberInput.text().strip()
        plain_line_number = self.view.plainLineNumberInput.text().strip()
        operators = "; ".join(value for value in operator_values if value) or None
        batch_label = self.view.batchLabelInput.text().strip()
        target_text = self.view.targetQuantityInput.text().strip()

        if not operator_number or not line_number:
            self.view.show_error("Operator # and Line are required to start a session.")
            return
        if target_text and not target_text.isdigit():
            self.view.show_error("Target quantity must be a positive whole number.")
            return

        target_quantity = int(target_text) if target_text else None

        db = SessionLocal()
        try:
            receipt = receipt_def_service.get_receipt_by_name(db, receipt_name)
            if receipt is None:
                self.view.show_error(f"No active receipt named '{receipt_name}' was found.")
                return
            if not operator_values[0]:
                self.view.show_error("Operator 1 is required to start a session.")
                return

            session = scan_service.start_scan_session(
                db,
                started_by_user_id=self.user.id,
                receipt_definition_id=receipt.id,
                operator_number=operator_number,
                line_number=line_number,
                plain_line_number=plain_line_number or None,
                batch_label=batch_label or None,
                operators=operators,
                target_quantity=target_quantity,
            )
            session_id = session.id
            companion_enabled = bool(receipt.companion_receipt_id and receipt.companion_required)
        except ValueError as e:
            self.view.show_error(str(e))
            return
        finally:
            db.close()

        self._scan_window = ScanWindow(
            session,
            receipt_name,
            companion_enabled=companion_enabled,
        )
        self._scan_controller = ScanController(self._scan_window, self.user, session_id)
        self._scan_window.destroyed.connect(self.refresh_session_followup)
        self._scan_window.show()
