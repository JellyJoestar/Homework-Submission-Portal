from flask_login import UserMixin
from werkzeug.security import check_password_hash


class User(UserMixin):
    def __init__(
        self,
        user_id: int,
        email: str,
        password_hash: str,
        role: str,
        first_name: str,
        last_name: str,
        created_at=None
    ) -> None:
        # Flask-Login reads `self.id` to know which user is stored in the session
        self.id = user_id
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.first_name = first_name
        self.last_name = last_name
        self.created_at = created_at

    @classmethod
    def from_row(cls, row):
        """
            Create a User instance from a mysql row (dictionary).
        """
        if row is None:
            return None

        return cls(**row)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def check_password(self, password: str) -> bool:
        """
            Verify a password in plain text against the stored hash
        """
        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles) -> bool:
        return self.role in roles
