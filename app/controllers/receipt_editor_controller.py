from datetime import datetime, timezone
from types import SimpleNamespace

from app.database.session import SessionLocal
from app.domain.exceptions import TemplateError
from app.domain.template_engine import compile_template, resolve_placeholder_value, SERIAL_PLACEHOLDER
from app.services import receipt_def_service, receipt_import_service
from app.views.token_dialogs import LiteralTokenDialog, PlaceholderTokenDialog, RegexTokenDialog

from PySide6.QtWidgets import QFileDialog
from PySide6.QtCore import Qt


# A fake ScanSession used only to render the live preview, so LineNumber /
# OpNumber / PlainLineNumber placeholders have something to resolve from.
_PREVIEW_SESSION = SimpleNamespace(
    operator_number="OP01", line_number="LINE01", plain_line_number="01",
)


class ReceiptEditorController:
    def __init__(self, view, user):
        self.view = view
        self.user = user
        self.current_receipt_id = None  # None => creating a new receipt

        self._load_receipt_list()
        self._load_companion_choices()
        self.view.clear_form()

        self.view.receiptList.currentItemChanged.connect(self.on_select_receipt)
        self.view.newButton.clicked.connect(self.on_new_receipt)
        self.view.importCsvButton.clicked.connect(self.on_import_csv)

        self.view.addLiteralButton.clicked.connect(self.on_add_literal)
        self.view.addPlaceholderButton.clicked.connect(self.on_add_placeholder)
        self.view.addRegexButton.clicked.connect(self.on_add_regex)
        self.view.moveUpButton.clicked.connect(self.on_move_up)
        self.view.moveDownButton.clicked.connect(self.on_move_down)
        self.view.removeTokenButton.clicked.connect(self.on_remove_token)

        self.view.saveButton.clicked.connect(self.on_save)
        self.view.closeButton.clicked.connect(self.view.close)

        # Any field edit refreshes the live preview.
        for edit in self.view.field_inputs.values():
            edit.textChanged.connect(self._update_preview)
        self.view.serialMinInput.textChanged.connect(self._update_preview)
        self.view.serialMaxInput.textChanged.connect(self._update_preview)

    # ---------------------------------------------------------------
    # Loading
    # ---------------------------------------------------------------
    def _load_receipt_list(self):
        db = SessionLocal()
        try:
            receipts = receipt_def_service.list_all_receipts(db)
            self.view.receiptList.blockSignals(True)
            self.view.receiptList.clear()
            for r in receipts:
                item_text = f"{r.name}  [{r.status}]"
                self.view.receiptList.addItem(item_text)
                self.view.receiptList.item(self.view.receiptList.count() - 1).setData(Qt.UserRole, r.id)
            self.view.receiptList.blockSignals(False)
        finally:
            db.close()

    def _load_companion_choices(self):
        db = SessionLocal()
        try:
            receipts = receipt_def_service.list_all_receipts(db)
            self.view.companionCombo.clear()
            self.view.companionCombo.addItem("(none)", userData=None)
            for r in receipts:
                if r.id != self.current_receipt_id:
                    self.view.companionCombo.addItem(r.name, userData=r.id)
        finally:
            db.close()

    # ---------------------------------------------------------------
    # Selecting / loading a receipt into the form
    # ---------------------------------------------------------------
    def on_select_receipt(self, current, previous):
        if current is None:
            return
        receipt_id = current.data(Qt.UserRole)
        db = SessionLocal()
        try:
            rd = receipt_def_service.get_receipt(db, receipt_id)
            if rd is None:
                return
            self._load_form_from_receipt(rd)
        finally:
            db.close()

    def _load_form_from_receipt(self, rd):
        self.current_receipt_id = rd.id
        self.view.nameInput.setText(rd.name or "")
        idx = self.view.statusCombo.findText(rd.status or "draft")
        self.view.statusCombo.setCurrentIndex(max(idx, 0))

        for field_name, edit in self.view.field_inputs.items():
            edit.setText(getattr(rd, field_name, "") or "")

        self.view.serialMinInput.setText("" if rd.serial_min is None else str(rd.serial_min))
        self.view.serialMaxInput.setText("" if rd.serial_max is None else str(rd.serial_max))

        idx = self.view.timestampPolicyCombo.findText(rd.timestamp_policy or "use_scan_time")
        self.view.timestampPolicyCombo.setCurrentIndex(max(idx, 0))

        self._load_companion_choices()
        if rd.companion_receipt_id:
            idx = self.view.companionCombo.findData(rd.companion_receipt_id)
            self.view.companionCombo.setCurrentIndex(max(idx, 0))
        else:
            self.view.companionCombo.setCurrentIndex(0)
        self.view.companionRequiredCheck.setChecked(bool(rd.companion_required))
        self.view.preventDuplicatesCheck.setChecked(bool(rd.prevent_duplicate_scans))
        self.view.autoGenerateBatchCheck.setChecked(bool(rd.auto_generate_batch_number))

        self.view.notesInput.setPlainText(rd.notes or "")
        self.view.set_tokens(rd.template_tokens or [])
        self._update_preview()

    def on_new_receipt(self):
        self.current_receipt_id = None
        self.view.receiptList.clearSelection()
        self.view.clear_form()
        self._load_companion_choices()

    def on_import_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.view, "Import Receipts from CSV", "", "CSV files (*.csv);;All files (*)"
        )
        if not file_path:
            return

        db = SessionLocal()
        try:
            report = receipt_import_service.import_csv(db, file_path, created_by_user_id=self.user.id)
        except Exception as e:
            self.view.show_error(f"Import failed: {e}")
            return
        finally:
            db.close()

        lines = [
            f"Created: {len(report['created'])}",
            f"Updated: {len(report['updated'])}",
            f"Errors: {len(report['errors'])}",
        ]
        if report["errors"]:
            lines.append("")
            lines.append("Errors:")
            for row_num, name, message in report["errors"][:20]:
                where = f"row {row_num}" if row_num else "companion link"
                label = f" ({name})" if name else ""
                lines.append(f"  - {where}{label}: {message}")
            if len(report["errors"]) > 20:
                lines.append(f"  ... and {len(report['errors']) - 20} more")

        if report["errors"] and not (report["created"] or report["updated"]):
            self.view.show_error("\n".join(lines))
        else:
            self.view.show_info("\n".join(lines))

        self._load_receipt_list()
        self._load_companion_choices()

    # ---------------------------------------------------------------
    # Token builder buttons
    # ---------------------------------------------------------------
    def on_add_literal(self):
        dlg = LiteralTokenDialog(self.view)
        if dlg.exec():
            self._append_token(dlg.token())

    def on_add_placeholder(self):
        dlg = PlaceholderTokenDialog(self.view)
        if dlg.exec():
            self._append_token(dlg.token())

    def on_add_regex(self):
        dlg = RegexTokenDialog(self.view)
        if dlg.exec():
            self._append_token(dlg.token())

    def _append_token(self, token):
        tokens = self.view.get_tokens()
        tokens.append(token)
        self.view.set_tokens(tokens)
        self._update_preview()

    def on_move_up(self):
        row = self.view.tokenList.currentRow()
        if row <= 0:
            return
        tokens = self.view.get_tokens()
        tokens[row - 1], tokens[row] = tokens[row], tokens[row - 1]
        self.view.set_tokens(tokens)
        self.view.tokenList.setCurrentRow(row - 1)
        self._update_preview()

    def on_move_down(self):
        row = self.view.tokenList.currentRow()
        tokens = self.view.get_tokens()
        if row < 0 or row >= len(tokens) - 1:
            return
        tokens[row + 1], tokens[row] = tokens[row], tokens[row + 1]
        self.view.set_tokens(tokens)
        self.view.tokenList.setCurrentRow(row + 1)
        self._update_preview()

    def on_remove_token(self):
        row = self.view.tokenList.currentRow()
        if row < 0:
            return
        tokens = self.view.get_tokens()
        del tokens[row]
        self.view.set_tokens(tokens)
        self._update_preview()

    # ---------------------------------------------------------------
    # Live preview
    # ---------------------------------------------------------------
    def _draft_receipt_from_form(self):
        """Builds an in-memory (unsaved) ReceiptDefinition-like object from
        whatever is currently in the form, for preview/validation only."""
        fields = {name: (edit.text() or None) for name, edit in self.view.field_inputs.items()}
        serial_min = self.view.serialMinInput.text().strip()
        serial_max = self.view.serialMaxInput.text().strip()
        return SimpleNamespace(
            name=self.view.nameInput.text(),
            status=self.view.statusCombo.currentText(),
            template_tokens=self.view.get_tokens(),
            serial_min=int(serial_min) if serial_min else None,
            serial_max=int(serial_max) if serial_max else None,
            timestamp_policy=self.view.timestampPolicyCombo.currentText(),
            frozen_timestamp=None,
            companion_receipt_id=self.view.companionCombo.currentData(),
            companion_required=self.view.companionRequiredCheck.isChecked(),
            prevent_duplicate_scans=self.view.preventDuplicatesCheck.isChecked(),
            auto_generate_batch_number=self.view.autoGenerateBatchCheck.isChecked(),
            **fields,
        )

    def _update_preview(self, *args):
        draft = self._draft_receipt_from_form()
        now = datetime.now(timezone.utc)
        pieces = []
        try:
            for tok in draft.template_tokens:
                if tok["type"] == "literal":
                    pieces.append(tok["value"])
                elif tok["type"] == "placeholder" and tok["name"] == SERIAL_PLACEHOLDER:
                    example = draft.serial_min if draft.serial_min is not None else 1
                    pieces.append(str(example))
                elif tok["type"] == "placeholder":
                    pieces.append(resolve_placeholder_value(tok["name"], draft, _PREVIEW_SESSION, now))
                elif tok["type"] == "regex":
                    pieces.append(f"<{tok['name']}>")
            self.view.previewLabel.setStyleSheet("color: #2a6; font-family: monospace;")
            self.view.previewLabel.setText("".join(pieces) or "(empty template)")
        except TemplateError as e:
            self.view.previewLabel.setStyleSheet("color: #c33; font-family: monospace;")
            self.view.previewLabel.setText(f"Template error: {e}")

    # ---------------------------------------------------------------
    # Save
    # ---------------------------------------------------------------
    def on_save(self):
        name = self.view.nameInput.text().strip()
        if not name:
            self.view.show_error("Name is required.")
            return

        tokens = self.view.get_tokens()
        if not tokens:
            self.view.show_error("Add at least one token to the template.")
            return

        # Validate the template actually compiles (catches invalid regex,
        # unknown placeholders, etc.) before saving.
        draft = self._draft_receipt_from_form()
        try:
            compile_template(draft, _PREVIEW_SESSION, datetime.now(timezone.utc))
        except TemplateError as e:
            self.view.show_error(f"Template doesn't compile: {e}")
            return

        serial_min_text = self.view.serialMinInput.text().strip()
        serial_max_text = self.view.serialMaxInput.text().strip()
        if serial_min_text and not serial_min_text.lstrip("-").isdigit():
            self.view.show_error("SerialNumber min must be a whole number.")
            return
        if serial_max_text and not serial_max_text.lstrip("-").isdigit():
            self.view.show_error("SerialNumber max must be a whole number.")
            return

        fields = dict(
            status=self.view.statusCombo.currentText(),
            template_tokens=tokens,
            serial_min=int(serial_min_text) if serial_min_text else None,
            serial_max=int(serial_max_text) if serial_max_text else None,
            timestamp_policy=self.view.timestampPolicyCombo.currentText(),
            companion_receipt_id=self.view.companionCombo.currentData(),
            companion_required=self.view.companionRequiredCheck.isChecked(),
            prevent_duplicate_scans=self.view.preventDuplicatesCheck.isChecked(),
            auto_generate_batch_number=self.view.autoGenerateBatchCheck.isChecked(),
            notes=self.view.notesInput.toPlainText() or None,
        )
        for field_name, edit in self.view.field_inputs.items():
            fields[field_name] = edit.text() or None

        db = SessionLocal()
        try:
            if self.current_receipt_id is None:
                rd = receipt_def_service.create_receipt(
                    db, name=name, created_by_user_id=self.user.id, **fields
                )
                self.current_receipt_id = rd.id
                self.view.show_info(f"Receipt '{name}' created.")
            else:
                fields["name"] = name
                receipt_def_service.update_receipt(db, self.current_receipt_id, **fields)
                self.view.show_info(f"Receipt '{name}' saved.")
        except ValueError as e:
            self.view.show_error(str(e))
            return
        finally:
            db.close()

        self._load_receipt_list()
        self._load_companion_choices()
