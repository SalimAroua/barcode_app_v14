from app.models import User
from app.models import roles
from app.utils.security import hash_password


def list_users(db):
    return db.query(User).order_by(User.username).all()


def get_user(db, user_id):
    return db.query(User).get(user_id)


def _active_superuser_count(db, exclude_user_id=None):
    q = db.query(User).filter(User.role == roles.SUPERUSER, User.active.is_(True))
    if exclude_user_id is not None:
        q = q.filter(User.id != exclude_user_id)
    return q.count()


def create_user(
    db, *, username, fullname, password, role, active=True,
    employee_id=None, team_leader=None, shift_leader=None,
):
    username = (username or "").strip()
    if not username:
        raise ValueError("Username is required.")
    if role not in roles.ALL_ROLES:
        raise ValueError(f"Unknown role: {role}")
    if not password:
        raise ValueError("Password is required.")

    existing = db.query(User).filter_by(username=username).first()
    if existing is not None:
        raise ValueError(f"A user named '{username}' already exists.")

    user = User(
        username=username,
        fullname=fullname or "",
        employee_id=employee_id or "",
        team_leader=team_leader or "",
        shift_leader=shift_leader or "",
        password_hash=hash_password(password),
        role=role,
        active=active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db, user_id, *, fullname=None, role=None, active=None,
    employee_id=None, team_leader=None, shift_leader=None, acting_user_id=None,
):
    """Updates profile/access fields. Refuses any change that would leave
    zero active SuperUsers (e.g. demoting or deactivating the last one),
    so an admin can never accidentally lock everyone out."""
    user = db.query(User).get(user_id)
    if user is None:
        raise ValueError("User not found.")

    would_be_role = role if role is not None else user.role
    would_be_active = active if active is not None else user.active

    currently_counts_as_active_superuser = (user.role == roles.SUPERUSER and user.active)
    would_still_count = (would_be_role == roles.SUPERUSER and would_be_active)

    if currently_counts_as_active_superuser and not would_still_count:
        remaining = _active_superuser_count(db, exclude_user_id=user.id)
        if remaining == 0:
            raise ValueError(
                "Can't change this user: they are the last active SuperUser. "
                "Promote/activate another SuperUser first."
            )

    if role is not None:
        if role not in roles.ALL_ROLES:
            raise ValueError(f"Unknown role: {role}")
        user.role = role
    if active is not None:
        user.active = active
    if fullname is not None:
        user.fullname = fullname
    if employee_id is not None:
        user.employee_id = employee_id
    if team_leader is not None:
        user.team_leader = team_leader
    if shift_leader is not None:
        user.shift_leader = shift_leader

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def reset_password(db, user_id, new_password):
    if not new_password:
        raise ValueError("Password is required.")
    user = db.query(User).get(user_id)
    if user is None:
        raise ValueError("User not found.")
    user.password_hash = hash_password(new_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
