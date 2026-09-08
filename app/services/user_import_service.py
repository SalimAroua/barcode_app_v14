"""Bulk import User accounts from a CSV file - one row per user.

Expected CSV header columns (username is required; the other columns are
optional): username, fullname, employee_id, team_leader, shift_leader,
password, role, active

Existing usernames are updated. A password is required when creating a new
user and is optional when updating an existing user; a blank update password
keeps the current password.
"""
import csv

from app.models import User
from app.services import user_service


REQUIRED_COLUMNS = {"username"}


def _parse_bool(value, default=True):
    if value is None or value == "":
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y")


def import_csv(db, file_path, acting_user_id=None):
    """Return created, updated, and per-row error details."""
    created, updated, errors = [], [], []

    with open(file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            errors.append((0, "", "File is empty or has no header row."))
            return {"created": created, "updated": updated, "errors": errors}

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            errors.append((0, "", f"Missing required column(s): {', '.join(sorted(missing))}"))
            return {"created": created, "updated": updated, "errors": errors}

        rows = list(reader)

    for row_num, row in enumerate(rows, start=2):
        username = (row.get("username") or "").strip()
        if not username:
            errors.append((row_num, "", "Missing 'username'."))
            continue

        fullname = (row.get("fullname") or "").strip()
        employee_id = (row.get("employee_id") or "").strip()
        team_leader = (row.get("team_leader") or "").strip()
        shift_leader = (row.get("shift_leader") or "").strip()
        password = row.get("password") or ""
        role = (row.get("role") or "Operator").strip()
        active = _parse_bool(row.get("active"))

        try:
            existing = db.query(User).filter_by(username=username).first()
            if existing is None:
                if not password:
                    raise ValueError("Password is required for a new user.")
                user_service.create_user(
                    db, username=username, fullname=fullname, password=password,
                    role=role, active=active,
                    employee_id=employee_id, team_leader=team_leader,
                    shift_leader=shift_leader,
                )
                created.append(username)
            else:
                user_service.update_user(
                    db, existing.id, fullname=fullname, role=role, active=active,
                    employee_id=employee_id, team_leader=team_leader,
                    shift_leader=shift_leader,
                    acting_user_id=acting_user_id,
                )
                if password:
                    user_service.reset_password(db, existing.id, password)
                updated.append(username)
        except ValueError as e:
            errors.append((row_num, username, str(e)))

    return {"created": created, "updated": updated, "errors": errors}