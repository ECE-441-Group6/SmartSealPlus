"""Create dashboard accounts without exposing public registration."""

import getpass
import sys

if __package__:
    from .auth import create_user
else:
    from auth import create_user

if __package__:
    from Gateway.database import init_database
else:
    from database import init_database


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "add":
        print("Usage: python -m Dashboard.manage_accounts add <username>")
        return 2

    username = sys.argv[2]
    password = getpass.getpass("New dashboard password (12+ characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 1

    init_database()
    try:
        create_user(username, password)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1

    print(f"Dashboard account '{username}' created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
