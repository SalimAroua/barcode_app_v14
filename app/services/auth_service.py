import config
from app.database.session import SessionLocal
from app.models.user import User
from app.utils.security import hash_password
from app.utils.security import verify_password


class AuthService:

    @staticmethod
    def create_superuser():

        db = SessionLocal()

        user = db.query(User).first()

        if user is None:

            admin = User(
                username=config.SEED_SUPERUSER_USERNAME,
                fullname="Super Administrator",
                password_hash=hash_password(config.SEED_SUPERUSER_PASSWORD),
                role="SuperUser",
                active=True
            )

            db.add(admin)
            db.commit()

            print("Default SuperUser created.")
            print(f"username : {config.SEED_SUPERUSER_USERNAME}")
            print(f"password : {config.SEED_SUPERUSER_PASSWORD}")

        db.close()

    @staticmethod
    def login(username, password):

        db = SessionLocal()

        user = (
            db.query(User)
            .filter(User.username == username)
            .first()
        )

        if not user:
            db.close()
            return None

        if not user.active:
            db.close()
            return None

        if verify_password(password, user.password_hash):
            db.close()
            return user

        db.close()
        return None