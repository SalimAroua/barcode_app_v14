from datetime import datetime, timezone

from PySide6.QtWidgets import QFileDialog
from PySide6.QtCore import Qt

from app.database.session import SessionLocal
from app.models import ReceiptDefinition, ScanSession
from app.services import export_service


class ExportController:
    def __init__(self, view):
        self.view = view

        self._load_sessions()
        self._load_receipts()

        self.view.exportButton.clicked.connect(self.on_export)
        self.view.closeButton.clicked.connect(self.view.close)

    def _load_sessions(self):
        db = SessionLocal()
        try:
            sessions = db.query(ScanSession).order_by(ScanSession.id.desc()).all()
            items = []
            for s in sessions:
                receipt_name = s.receipt_definition.name if s.receipt_definition else "?"
                status = "active" if s.is_active else "ended"
                started = s.started_at.strftime("%Y-%m-%d %H:%M") if s.started_at else "?"
                label = f"#{s.id}  {receipt_name}  op:{s.operator_number} line:{s.line_number}  {started}  [{status}]"
                items.append((s.id, label))
            self.view.set_session_list(items)
        finally:
            db.close()

    def _load_receipts(self):
        db = SessionLocal()
        try:
            receipts = db.query(ReceiptDefinition).order_by(ReceiptDefinition.name).all()
            items = [(r.id, f"{r.name}  [{r.status}]") for r in receipts]
            self.view.set_receipt_list(items)
        finally:
            db.close()

    def on_export(self):
        fmt = self.view.formatCombo.currentText().lower()
        ext = "csv" if fmt == "csv" else "xlsx"
        filter_str = "CSV files (*.csv)" if fmt == "csv" else "Excel files (*.xlsx)"

        file_path, _ = QFileDialog.getSaveFileName(
            self.view, "Export Scan History", f"scan_history.{ext}", filter_str
        )
        if not file_path:
            return
        if not file_path.lower().endswith(f".{ext}"):
            file_path += f".{ext}"

        mode_index = self.view.modeCombo.currentIndex()
        db = SessionLocal()
        try:
            if mode_index == 0:
                item = self.view.sessionList.currentItem()
                if item is None:
                    self.view.show_error("Pick a session to export.")
                    return
                session_id = item.data(Qt.UserRole)
                count = export_service.export_session(db, session_id, file_path, fmt=fmt)
            else:
                receipt_id = self.view.receiptCombo.currentData()
                if receipt_id is None:
                    self.view.show_error("Pick a receipt to export.")
                    return
                start_dt = self.view.startDateTime.dateTime().toPython().replace(tzinfo=timezone.utc)
                end_dt = self.view.endDateTime.dateTime().toPython().replace(tzinfo=timezone.utc)
                if start_dt > end_dt:
                    self.view.show_error("'From' date must be before 'To' date.")
                    return
                count = export_service.export_receipt_daterange(db, receipt_id, start_dt, end_dt, file_path, fmt=fmt)
        except Exception as e:
            self.view.show_error(f"Export failed: {e}")
            return
        finally:
            db.close()

        self.view.show_info(f"Exported {count} scan event(s) to:\n{file_path}")
