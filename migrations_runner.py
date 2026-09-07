"""
Programmatic access to Alembic, so `python main.py` (and test scripts)
can bring the database schema up to the latest revision without the
person needing to run `alembic upgrade head` by hand first.
"""
import os
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect


def _bundle_root():
    """Where alembic.ini and migrations/ can be found: the PyInstaller
    extraction directory when frozen (these are bundled as 'datas', see
    main.spec), or this file's own directory when running from source.
    Deliberately NOT using __file__ when frozen - for a pure-Python module
    bundled into PyInstaller's PYZ archive, __file__ isn't guaranteed to
    be a real path on disk.
    """
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


_PROJECT_ROOT = _bundle_root()
_ALEMBIC_INI = os.path.join(_PROJECT_ROOT, "alembic.ini")

# The very first migration - matches migrations/versions/a7aec50bc2aa_*.py.
# Used to "stamp" pre-existing databases that were created by an older
# version of this app (via Base.metadata.create_all(), before Alembic was
# introduced) so Alembic knows not to try to re-create tables that are
# already there.
_BASELINE_REVISION = "a7aec50bc2aa"

# Tables that only exist if the DB was already set up by this app (any
# version) before Alembic tracking was added.
_KNOWN_APP_TABLES = {"users", "receipt_definitions", "scan_sessions", "scan_events", "scan_units"}


def get_alembic_config():
    cfg = Config(_ALEMBIC_INI)
    cfg.set_main_option("script_location", os.path.join(_PROJECT_ROOT, "migrations"))
    return cfg


def run_migrations_to_head():
    """Idempotent: safe to call on every app startup, whether the DB is
    brand new, already at head, already tracked but a few revisions
    behind, or - the tricky case - an existing database created by an
    older, pre-Alembic version of this app (create_all()), which has our
    tables already but no recorded Alembic revision yet.

    Checking the current revision (rather than just whether the
    alembic_version TABLE exists) matters because SQLite DDL isn't
    transactional: a previously failed migration attempt can leave behind
    an empty alembic_version table with no row in it. Table-existence alone
    would mistake that for "already tracked" and skip stamping, then hit
    the exact same CREATE TABLE collision again.
    """
    from alembic.runtime.migration import MigrationContext
    from app.database.database import engine  # imported lazily to avoid import cycles

    cfg = get_alembic_config()

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.connect() as conn:
        current_revision = MigrationContext.configure(conn).get_current_revision()

    if current_revision is None and existing_tables & _KNOWN_APP_TABLES:
        # Pre-Alembic (or partially-migrated) database: the schema already
        # matches the baseline (every version of this app before now used
        # create_all() with the full current model set), so mark it as
        # such rather than trying to CREATE TABLE things that already exist.
        print(
            "Detected an existing database with no recorded migration history. "
            "Marking it as up to date with the baseline schema (no data is touched)."
        )
        command.stamp(cfg, _BASELINE_REVISION)

    command.upgrade(cfg, "head")
