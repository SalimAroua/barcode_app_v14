"""Render ZPL to PDF for an in-app preview.

The production print path sends raw ZPL directly to a Zebra printer. Preview
uses Labelary's ZPL renderer so a developer/operator can inspect the real
rendered label without a physical printer.
"""
from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_DPI = 8
DEFAULT_LABEL_SIZE = "4x6"
DEFAULT_API_BASE = "https://api.labelary.com/v1/printers"


class ZplPreviewError(RuntimeError):
    """Raised when the remote ZPL renderer cannot produce a PDF."""


def render_zpl_to_pdf(zpl_bytes: bytes, *, dpi: int = DEFAULT_DPI,
                       label_size: str = DEFAULT_LABEL_SIZE,
                       timeout: float = 20.0) -> bytes:
    if not zpl_bytes or b"^XA" not in zpl_bytes.upper():
        raise ZplPreviewError("The label does not contain a valid ^XA ... ^XZ ZPL format.")
    if dpi not in (6, 8, 12, 24):
        raise ZplPreviewError("Preview DPI must be 6, 8, 12, or 24.")
    if not label_size or "x" not in label_size.lower():
        raise ZplPreviewError("Label size must use the form WIDTHxHEIGHT, for example 4x6.")

    url = f"{DEFAULT_API_BASE}/{dpi}dpmm/labels/{label_size}/0/"
    request = urllib.request.Request(
        url,
        data=zpl_bytes,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/pdf",
            "User-Agent": "BarcodeApp-ZPL-Preview/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=float(timeout)) as response:
            payload = response.read()
            content_type = response.headers.get_content_type()
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            detail = ""
        raise ZplPreviewError(
            f"ZPL renderer returned HTTP {exc.code}. {detail[:400]}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ZplPreviewError(
            "Could not contact the ZPL preview renderer. Check the internet connection "
            f"or try again later. Details: {exc}"
        ) from exc

    if content_type != "application/pdf" or not payload.startswith(b"%PDF"):
        raise ZplPreviewError("The ZPL renderer returned an invalid PDF response.")
    return payload


def render_zpl_file_to_pdf(zpl_path: str, *, dpi: int = DEFAULT_DPI,
                           label_size: str = DEFAULT_LABEL_SIZE,
                           timeout: float = 20.0) -> bytes:
    path = Path(zpl_path)
    if not path.exists():
        raise ZplPreviewError(f"ZPL file not found: {path}")
    try:
        zpl_bytes = path.read_bytes()
    except OSError as exc:
        raise ZplPreviewError(f"Could not read ZPL file: {exc}") from exc
    return render_zpl_to_pdf(zpl_bytes, dpi=dpi, label_size=label_size, timeout=timeout)
