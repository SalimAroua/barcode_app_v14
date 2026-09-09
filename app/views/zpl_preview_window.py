from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout,
)

from app.services import zpl_preview_service

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
    HAS_QT_PDF = True
except ImportError:
    HAS_QT_PDF = False


class ZplPreviewWindow(QDialog):
    """Render and display a ZPL label as a real PDF inside the application."""

    def __init__(self, zpl_path, parent=None):
        super().__init__(parent)
        self.zpl_path = zpl_path
        self.pdf_bytes = None
        self.pdf_path = None
        self._pdf_document = None
        self._pdf_buffer = None
        self.setWindowTitle("ZPL Label Preview")
        self.resize(760, 900)

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(f"Template: {Path(zpl_path).name}"))
        top.addStretch()
        top.addWidget(QLabel("DPI"))
        self.dpiCombo = QComboBox()
        for dpi in (6, 8, 12, 24):
            self.dpiCombo.addItem(str(dpi), dpi)
        self.dpiCombo.setCurrentIndex(1)
        top.addWidget(self.dpiCombo)
        top.addWidget(QLabel("Size"))
        self.sizeCombo = QComboBox()
        self.sizeCombo.addItems(["4x6", "4x4", "3x5", "2x1"])
        top.addWidget(self.sizeCombo)
        self.renderButton = QPushButton("Render preview")
        top.addWidget(self.renderButton)
        layout.addLayout(top)

        self.statusLabel = QLabel("Ready")
        self.statusLabel.setWordWrap(True)
        layout.addWidget(self.statusLabel)

        self.saveButton = QPushButton("Save PDF...")
        self.saveButton.setEnabled(False)
        self.saveButton.clicked.connect(self.save_pdf)
        self.renderButton.clicked.connect(self.render)
        layout.addWidget(self.saveButton, alignment=Qt.AlignRight)

        if HAS_QT_PDF:
            self.viewer = QPdfView(self)
            self.viewer.setPageMode(QPdfView.PageMode.SinglePage)
            self.viewer.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            layout.addWidget(self.viewer, 1)
        else:
            self.viewer = QLabel(
                "Qt PDF support is not available in this PySide6 installation. "
                "The preview can still be saved as a PDF."
            )
            self.viewer.setAlignment(Qt.AlignCenter)
            self.viewer.setWordWrap(True)
            layout.addWidget(self.viewer, 1)

        self.render()

    def render(self):
        self.renderButton.setEnabled(False)
        self.statusLabel.setText("Rendering ZPL to PDF...")
        try:
            self.pdf_bytes = zpl_preview_service.render_zpl_file_to_pdf(
                self.zpl_path,
                dpi=self.dpiCombo.currentData(),
                label_size=self.sizeCombo.currentText(),
            )
            self._display_pdf()
            self.saveButton.setEnabled(True)
            self.statusLabel.setText("Preview rendered successfully.")
        except zpl_preview_service.ZplPreviewError as exc:
            self.pdf_bytes = None
            self.saveButton.setEnabled(False)
            self.statusLabel.setText(str(exc))
            QMessageBox.warning(self, "ZPL Preview", str(exc))
        finally:
            self.renderButton.setEnabled(True)

    def _display_pdf(self):
        if HAS_QT_PDF:
            self._pdf_document = QPdfDocument(self)
            self._pdf_buffer = QBuffer(self)
            self._pdf_buffer.setData(self.pdf_bytes)
            self._pdf_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self._pdf_document.load(self._pdf_buffer)
            self.viewer.setDocument(self._pdf_document)
        else:
            # Best-effort fallback: display the first PDF page as an image is
            # intentionally omitted; PDF remains available through Save PDF.
            self.viewer.setText(
                "PDF generated successfully. Click 'Save PDF...' to open it in your PDF viewer."
            )

    def save_pdf(self):
        if not self.pdf_bytes:
            return
        default_name = Path(self.zpl_path).with_suffix(".pdf").name
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save rendered label", default_name, "PDF files (*.pdf)"
        )
        if not file_path:
            return
        try:
            Path(file_path).write_bytes(self.pdf_bytes)
        except OSError as exc:
            QMessageBox.warning(self, "Save PDF", f"Could not save PDF: {exc}")
            return
        self.pdf_path = file_path
        self.statusLabel.setText(f"PDF saved: {file_path}")
