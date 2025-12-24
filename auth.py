import bcrypt
from flask_login import UserMixin
from db import get_db_connection

class User(UserMixin):
    def __init__(self, row: dict):
        self.id = row["id"]
        self.username = row["username"]
        self.role = row["role"]
        self.active = row["is_active"]  # <-- store it under a different name

    def is_active(self):
        # Flask-Login calls this to decide if the account is allowed to login
        return bool(self.active)

    @staticmethod
    def get(user_id: int):
        with get_db_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = %s;", (user_id,)).fetchone()
        return User(row) if row else None

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
