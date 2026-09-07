"""
Central configuration for the Barcode Placeholder App.
Values can be overridden with environment variables (see .env.example).
"""
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _app_base_dir():
    """Directory the app 'lives in': the folder containing the .exe when
    packaged with PyInstaller, or the folder containing this file when
    running from source. Used only as the default DB location, so the
    same barcode.db is found every time regardless of what directory the
    app happens to be launched from (double-click, shortcut, terminal,
    etc. can all have different working directories).
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


_DEFAULT_DB_PATH = os.path.join(_app_base_dir(), "barcode.db")

# --- Database -----------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"

# --- Seeding --------------------------------------------------------------
SEED_SUPERUSER_USERNAME = os.getenv("SEED_SUPERUSER_USERNAME", "admin")
SEED_SUPERUSER_PASSWORD = os.getenv("SEED_SUPERUSER_PASSWORD", "admin123")

# --- Serial number defaults ------------------------------------------------
# Used only when a receipt definition doesn't set its own bounds.
DEFAULT_SERIAL_MIN = 0
DEFAULT_SERIAL_MAX = 9_999_999
