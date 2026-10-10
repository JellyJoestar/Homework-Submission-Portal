"""Functional tests for IFN636-87: passwords are stored as hashes, never as plain text."""
from werkzeug.security import generate_password_hash

from conftest import PASSWORD
from models import User


def test_password_hash_is_not_the_password():
    password_hash = generate_password_hash(PASSWORD)

    assert password_hash != PASSWORD
    assert password_hash.startswith("scrypt:")


def test_user_can_only_log_in_with_the_right_password():
    user = User(1, "teacher@portal.edu.au", generate_password_hash(PASSWORD), "Teacher", "Tess", "Teacher")

    assert user.check_password(PASSWORD)
    assert not user.check_password("WrongPassword1!")
