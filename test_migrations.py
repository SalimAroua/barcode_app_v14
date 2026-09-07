"""
Tests for the Alembic migration setup:
 - upgrading a brand-new DB creates exactly the expected tables/columns
 - running upgrade head twice is a safe no-op the second time
 - downgrade(base) -> upgrade(head) round-trips cleanly (drops + recreates)
 - a real "add a column" migration preserves existing row data (the whole
   point of using migrations instead of create_all())

Run with: python test_migrations.py
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///test_migrations.db"
if os.path.exists("test_migrations.db"):
    os.remove("test_migrations.db")

import sqlite3  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402
from alembic import command  # noqa: E402

from migrations_runner import get_alembic_config, run_migrations_to_head  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
import app.models  # noqa: E402
from app.database.database import engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models import ReceiptDefinition  # noqa: E402

results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


def current_head_revision(cfg):
    """Resolves to whatever the latest migration file's revision id is,
    so this test doesn't need editing every time a new migration is added."""
    return ScriptDirectory.from_config(cfg).get_current_head()


# --- 1. Upgrading a brand-new DB creates the expected schema ---
run_migrations_to_head()

inspector = inspect(engine)
tables = set(inspector.get_table_names())
expected_tables = {"users", "receipt_definitions", "scan_sessions", "scan_events", "scan_units",
                   "line_batch_counters", "alembic_version"}
check("All expected tables exist after upgrade head", expected_tables.issubset(tables))

receipt_columns = {c["name"] for c in inspector.get_columns("receipt_definitions")}
check("ReceiptDefinition has product_designation column", "product_designation" in receipt_columns)
check("ReceiptDefinition has serial_min/serial_max columns", {"serial_min", "serial_max"}.issubset(receipt_columns))
check("ReceiptDefinition has prevent_duplicate_scans column", "prevent_duplicate_scans" in receipt_columns)
check("ReceiptDefinition has template_file_path column", "template_file_path" in receipt_columns)
check("ReceiptDefinition has target_quantity column", "target_quantity" in receipt_columns)

scan_session_columns = {c["name"] for c in inspector.get_columns("scan_sessions")}
check("ScanSession has operators column", "operators" in scan_session_columns)
check("ScanSession has target_quantity column", "target_quantity" in scan_session_columns)
check("ScanSession has printed_label_path column", "printed_label_path" in scan_session_columns)

cfg = get_alembic_config()
expected_head = current_head_revision(cfg)

with engine.connect() as conn:
    version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
check("alembic_version table records the current head revision", version == expected_head)

# --- 2. Running upgrade head again is a safe no-op ---
run_migrations_to_head()  # should not raise, should not change anything
with engine.connect() as conn:
    version_again = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
check("Re-running upgrade head is idempotent", version_again == version)

# --- 3. Put some real data in, then do a downgrade -> upgrade round trip ---
db = SessionLocal()
rd = ReceiptDefinition(
    name="MIGRATION_TEST_RECEIPT", status="active",
    template_tokens=[{"type": "literal", "value": "X"}],
)
db.add(rd)
db.commit()
db.close()

cfg = get_alembic_config()
command.downgrade(cfg, "base")

inspector = inspect(engine)
tables_after_downgrade = set(inspector.get_table_names())
check("Downgrade to base removes the app tables", "receipt_definitions" not in tables_after_downgrade)

command.upgrade(cfg, "head")
inspector = inspect(engine)
tables_after_reupgrade = set(inspector.get_table_names())
check("Re-upgrading after downgrade recreates all tables", expected_tables.issubset(tables_after_reupgrade))

db = SessionLocal()
count_after = db.query(ReceiptDefinition).count()
db.close()
check("Downgrade+upgrade is a clean rebuild (old data is gone, as expected for a full rebuild)", count_after == 0)

# --- 4. Real schema-change scenario: add a column via a new migration,
#     confirm existing row data survives (unlike create_all(), which
#     can't alter existing tables at all).
db = SessionLocal()
rd2 = ReceiptDefinition(
    name="PRE_MIGRATION_ROW", status="active",
    template_tokens=[{"type": "literal", "value": "Y"}],
    part_number="PN-KEEP-ME",
)
db.add(rd2)
db.commit()
db.close()

versions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations", "versions")
test_migration_path = os.path.join(versions_dir, "zzz_test_add_test_column.py")
with open(test_migration_path, "w") as f:
    f.write(f'''
"""test: add a throwaway column"""
from alembic import op
import sqlalchemy as sa

revision = "test_add_col_0001"
down_revision = "{expected_head}"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("receipt_definitions") as batch_op:
        batch_op.add_column(sa.Column("test_throwaway_column", sa.String(50), nullable=True))


def downgrade():
    with op.batch_alter_table("receipt_definitions") as batch_op:
        batch_op.drop_column("test_throwaway_column")
''')

try:
    command.upgrade(cfg, "head")
    inspector = inspect(engine)
    receipt_columns_after = {c["name"] for c in inspector.get_columns("receipt_definitions")}
    check("New column added by the migration", "test_throwaway_column" in receipt_columns_after)

    db = SessionLocal()
    preserved = db.query(ReceiptDefinition).filter_by(name="PRE_MIGRATION_ROW").first()
    check("Existing row data survives a schema-adding migration (the whole point vs. create_all())",
          preserved is not None and preserved.part_number == "PN-KEEP-ME")
    db.close()

    command.downgrade(cfg, expected_head)
    inspector = inspect(engine)
    receipt_columns_reverted = {c["name"] for c in inspector.get_columns("receipt_definitions")}
    check("Downgrade removes the added column again", "test_throwaway_column" not in receipt_columns_reverted)

    db = SessionLocal()
    still_there = db.query(ReceiptDefinition).filter_by(name="PRE_MIGRATION_ROW").first()
    check("Row data survives the downgrade too", still_there is not None and still_there.part_number == "PN-KEEP-ME")
    db.close()
finally:
    os.remove(test_migration_path)
    command.upgrade(cfg, "head")  # leave the DB at head, matching every other test

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")

engine.dispose()
os.remove("test_migrations.db")
