"""Account storage and password helpers for the local dashboard."""

import re
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

if __package__:
    from Gateway.database import DB_NAME
else:
    from database import DB_NAME


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


def create_user(username, password):
    username = username.strip()
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "Username must be 3-32 characters: letters, numbers, dot, dash, underscore."
        )
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")

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
    conn = sqlite3.connect(DB_NAME)
    try:
        row = conn.execute(
            "SELECT username, password_hash FROM dashboard_users "
            "WHERE username = ? COLLATE NOCASE",
            (username.strip(),),
        ).fetchone()
    finally:
        conn.close()

    if row is None or not check_password_hash(row[1], password):
        return None
    return row[0]
