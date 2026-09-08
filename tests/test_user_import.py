"""Headless tests for user CSV import."""
import csv
import os

os.environ["DATABASE_URL"] = "sqlite:///test_user_import.db"
if os.path.exists("test_user_import.db"):
    os.remove("test_user_import.db")

import app.models  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.services import user_import_service  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402


Base.metadata.create_all(engine)
AuthService.create_superuser()


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "username", "fullname", "employee_id", "team_leader", "shift_leader",
            "password", "role", "active",
        ])
        writer.writeheader()
        writer.writerows(rows)


write_csv("test_users.csv", [
    {"username": "csvuser", "fullname": "CSV User", "employee_id": "EMP-001",
     "team_leader": "Team Lead One", "shift_leader": "Shift Lead One",
     "password": "secret123", "role": "Operator", "active": "true"},
    {"username": "csvadmin", "fullname": "CSV Admin", "employee_id": "EMP-002",
     "team_leader": "Team Lead Two", "shift_leader": "Shift Lead Two",
     "password": "admin123", "role": "Admin", "active": "1"},
])
db = SessionLocal()
report = user_import_service.import_csv(db, "test_users.csv")
assert set(report["created"]) == {"csvuser", "csvadmin"}
assert report["errors"] == []
db.close()
assert AuthService.login("csvuser", "secret123") is not None
db = SessionLocal()
user = db.query(User).filter_by(username="csvuser").first()
assert user.employee_id == "EMP-001"
assert user.team_leader == "Team Lead One"
assert user.shift_leader == "Shift Lead One"
db.close()

write_csv("test_users_update.csv", [
    {"username": "csvuser", "fullname": "Updated CSV User", "employee_id": "EMP-009",
     "team_leader": "New Team Lead", "shift_leader": "New Shift Lead",
     "password": "", "role": "Admin", "active": "false"},
])
db = SessionLocal()
report = user_import_service.import_csv(db, "test_users_update.csv")
user = db.query(User).filter_by(username="csvuser").first()
assert report["updated"] == ["csvuser"]
assert user.fullname == "Updated CSV User"
assert user.role == "Admin"
assert user.active is False
assert user.employee_id == "EMP-009"
assert user.team_leader == "New Team Lead"
assert user.shift_leader == "New Shift Lead"
db.close()
assert AuthService.login("csvuser", "secret123") is None

write_csv("test_users_bad.csv", [
    {"username": "", "fullname": "", "password": "", "role": "Operator", "active": "true"},
    {"username": "missingpassword", "fullname": "", "password": "", "role": "Operator", "active": "true"},
])
db = SessionLocal()
report = user_import_service.import_csv(db, "test_users_bad.csv")
assert len(report["errors"]) == 2
assert db.query(User).filter_by(username="missingpassword").first() is None
db.close()

engine.dispose()
for path in ["test_users.csv", "test_users_update.csv", "test_users_bad.csv", "test_user_import.db"]:
    if os.path.exists(path):
        os.remove(path)

print("User CSV import tests passed")