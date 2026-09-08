import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon


def app_resource_path(relative_path):
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(root, relative_path)


def set_app_icon(window):
    icon_path = app_resource_path("assets/sa_logo_barcode.png")
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))


def enable_maximize(window):
    """Keep the standard maximize button while preserving normal launch size."""
    window.setWindowFlag(Qt.WindowMaximizeButtonHint, True)