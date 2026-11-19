"""Account storage and password helpers for the local dashboard."""

import re
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

if __package__:
    from Gateway.database import DB_NAME
else:
    from database import DB_NAME


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
# Use the same scrypt cost for unknown usernames so login timing does not
# disclose whether an account name exists.
_DUMMY_PASSWORD_HASH = generate_password_hash(
    "SmartSeal-invalid-account-password-placeholder",
    method="scrypt",
)


def create_user(username, password):
    if not isinstance(username, str) or not isinstance(password, str):
        raise ValueError("Username and password must be text.")
    username = username.strip()
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "Username must be 3-32 characters: letters, numbers, dot, dash, underscore."
        )
    if not 12 <= len(password) <= 1024:
        raise ValueError("Password must be 12-1024 characters.")

    password_hash = generate_password_hash(password, method="scrypt")
    conn = sqlite3.connect(DB_NAME)
    try:
        with conn:
            conn.execute(
                "INSERT INTO dashboard_users(username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
    except sqlite3.IntegrityError as error:
        raise ValueError("That dashboard account already exists.") from error
    finally:
        conn.close()


def verify_user(username, password):
    if (
        not isinstance(username, str)
        or len(username) > 256
        or not isinstance(password, str)
        or len(password) > 1024
    ):
        return None

    conn = sqlite3.connect(DB_NAME)
    try:
        row = conn.execute(
            "SELECT username, password_hash FROM dashboard_users "
            "WHERE username = ? COLLATE NOCASE",
            (username.strip(),),
        ).fetchone()
    finally:
        conn.close()

    password_hash = row[1] if row is not None else _DUMMY_PASSWORD_HASH
    password_matches = check_password_hash(password_hash, password)
    if row is None or not password_matches:
        return None
    return row[0]
