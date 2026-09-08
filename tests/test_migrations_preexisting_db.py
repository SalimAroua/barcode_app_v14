"""
Regression test for a real bug reported by the user: running the app
against an existing database that was created by an OLDER, pre-Alembic
version of this app (via Base.metadata.create_all()) crashed with
"table users already exists", because Alembic didn't know that database
was already at the baseline schema.

Run with: python -m tests.test_migrations_preexisting_db
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///test_preexisting.db"
if os.path.exists("test_preexisting.db"):
    os.remove("test_preexisting.db")

from sqlalchemy import inspect, text  # noqa: E402
import app.models  # noqa: E402
from app.database.database import engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.utils.security import hash_password  # noqa: E402
from migrations_runner import get_alembic_config, run_migrations_to_head  # noqa: E402
from alembic import command  # noqa: E402

results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


# --- Step 1: simulate an existing pre-Alembic database, exactly like an
# older version of main.py would have made with create_all() at THAT
# time - i.e. only the original baseline schema, none of the columns
# added by later migrations. Built via the baseline migration itself
# (not create_all() against the CURRENT models, which would already
# include every column added since - that would defeat the point of this
# test for every column added after the first one), then the tracking
# table is dropped to simulate "Alembic never touched this database". ---
cfg = get_alembic_config()
command.upgrade(cfg, "a7aec50bc2aa")
with engine.connect() as conn:
    conn.execute(text("DROP TABLE alembic_version"))
    conn.commit()

db = SessionLocal()
db.add(User(username="admin", fullname="Super Administrator",
             password_hash=hash_password("admin123"), role="SuperUser", active=True))
db.commit()
db.close()

inspector = inspect(engine)
check("Simulated pre-existing DB has no alembic_version table yet",
      "alembic_version" not in set(inspector.get_table_names()))
check("Simulated pre-existing DB already has the users table",
      "users" in set(inspector.get_table_names()))
check("Simulated pre-existing DB does NOT yet have later-added columns (that's the point)",
      "prevent_duplicate_scans" not in {c["name"] for c in inspector.get_columns("receipt_definitions")})

# --- Step 2: this is exactly what main.py does on startup. Before the
# fix, this raised OperationalError: table users already exists. ---
crashed = False
try:
    run_migrations_to_head()
except Exception as e:
    crashed = True
    print(f"CRASHED: {e}")

check("run_migrations_to_head() does NOT crash on a pre-existing DB", not crashed)

# --- Step 3: confirm it stamped correctly, upgraded to head (later
# columns now present), and the existing data is untouched ---
inspector = inspect(engine)
check("alembic_version table now exists (DB is now tracked)",
      "alembic_version" in set(inspector.get_table_names()))
check("Later migrations applied on top of the stamp (new column now present)",
      "prevent_duplicate_scans" in {c["name"] for c in inspector.get_columns("receipt_definitions")})

db = SessionLocal()
admin = db.query(User).filter_by(username="admin").first()
check("Pre-existing admin user is untouched", admin is not None and admin.role == "SuperUser")
db.close()

# --- Step 4: running it again (simulating the next app launch) is a safe no-op ---
crashed_again = False
try:
    run_migrations_to_head()
except Exception as e:
    crashed_again = True
    print(f"CRASHED on second run: {e}")
check("Running it again afterward is still a safe no-op", not crashed_again)

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")

engine.dispose()
os.remove("test_preexisting.db")
