from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

from app.database.session import SessionLocal
from app.domain.exceptions import (
    IncompletePairError, InactiveScanSessionError, PrinterError, TemplateError,
)
from app.services import scan_service
from app.views.zpl_preview_window import ZplPreviewWindow


class ScanController:
    def __init__(self, view, user, scan_session_id):
        self.view = view
        self.user = user
        self.scan_session_id = scan_session_id

        self.view.scanInput.returnPressed.connect(
            lambda: self.on_scan(self.view.scanInput, "primary")
        )
        self.view.companionScanInput.returnPressed.connect(
            lambda: self.on_scan(self.view.companionScanInput, "companion")
        )
        self.view.endSessionButton.clicked.connect(self.on_end_session)
        self.view.reprintLabelButton.clicked.connect(self.on_reprint_label)
        self.view.previewLabelButton.clicked.connect(self.on_preview_label)
        self.view.set_reprint_available(self.user.role in ("Admin", "SuperUser"))

        db = SessionLocal()
        try:
            session, successful_count = scan_service.get_scan_session_status(db, self.scan_session_id)
            self.view.update_session_status(session, successful_count)
            self.view.update_metrics(scan_service.get_scan_session_metrics(db, self.scan_session_id))
            self.view.configure_companion_mode(bool(
                session.receipt_definition.companion_receipt_id
                and session.receipt_definition.companion_required
            ))
        finally:
            db.close()

    def on_scan(self, input_widget=None, expected_receipt=None):
        input_widget = input_widget or self.view.scanInput
        scanned_value = input_widget.text().strip()
        if not scanned_value:
            return

        db = SessionLocal()
        try:
            try:
                event, unit = scan_service.record_scan_event(
                    db,
                    user_id=self.user.id,
                    scan_session_id=self.scan_session_id,
                    scanned_value=scanned_value,
                    expected_receipt=expected_receipt,
                )
            except IncompletePairError:
                self.view.show_result(False, "IncompletePair")
                self.view.add_log_entry(scanned_value, False, "IncompletePair - scan the companion label first")
                input_widget.clear()
                input_widget.setFocus()
                return
            except TemplateError as e:
                QMessageBox.critical(self.view, "Template error", str(e))
                input_widget.clear()
                input_widget.setFocus()
                return
            except PrinterError as e:
                self.view.show_printer_error(str(e))
                input_widget.clear()
                input_widget.setFocus()
                return
            except InactiveScanSessionError as e:
                self.view.stop_scanning(str(e))
                return

            unit_info = ""
            if unit is not None:
                unit_info = "(unit complete)" if unit.is_complete else "(waiting for companion)"

            self.view.show_result(event.result_ok, event.failure_reason)
            self.view.add_log_entry(scanned_value, event.result_ok, event.failure_reason, unit_info)
            session, successful_count = scan_service.get_scan_session_status(db, self.scan_session_id)
            self.view.update_session_status(session, successful_count)
            self.view.update_metrics(scan_service.get_scan_session_metrics(db, self.scan_session_id))
            companion_enabled = bool(
                session.receipt_definition.companion_receipt_id
                and session.receipt_definition.companion_required
            )
            self.view.configure_companion_mode(companion_enabled)
            if expected_receipt == "primary" and companion_enabled:
                self.view.focus_companion_input()
            else:
                self.view.focus_primary_input()
        finally:
            db.close()

    def on_end_session(self):
        db = SessionLocal()
        try:
            scan_service.end_scan_session(db, self.scan_session_id)
        finally:
            db.close()
        self.view.close()

    def on_preview_label(self):
        db = SessionLocal()
        try:
            session, _ = scan_service.get_scan_session_status(db, self.scan_session_id)
            receipt = session.receipt_definition
            if receipt is None or not receipt.template_file_path:
                QMessageBox.warning(
                    self.view,
                    "ZPL Preview",
                    "This receipt does not have a ZPL template file configured.",
                )
                return

            # Render the same concrete ZPL used by the real print path.
            zpl_path = scan_service.render_label_for_preview(session, receipt)
        except Exception as exc:
            QMessageBox.warning(self.view, "ZPL Preview", str(exc))
            return
        finally:
            db.close()

        self._preview_window = ZplPreviewWindow(zpl_path, self.view)
        self._preview_window.setAttribute(Qt.WA_DeleteOnClose, True)
        self._preview_window.show()

    def on_reprint_label(self):
        db = SessionLocal()
        try:
            path = scan_service.reprint_label(
                db,
                scan_session_id=self.scan_session_id,
                requesting_role=self.user.role,
            )
            session, successful_count = scan_service.get_scan_session_status(db, self.scan_session_id)
            self.view.update_session_status(session, successful_count)
            self.view.update_metrics(scan_service.get_scan_session_metrics(db, self.scan_session_id))
            QMessageBox.information(self.view, "Label reprinted", f"Label written to:\n{path}")
        except (PermissionError, ValueError) as e:
            QMessageBox.warning(self.view, "Reprint unavailable", str(e))
        except PrinterError as e:
            self.view.show_printer_error(str(e))
        finally:
            db.close()
