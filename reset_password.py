#!/usr/bin/env python
"""Reset a FireFleet HQ user's password from the command line."""
from __future__ import annotations

import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User

MIN_PASSWORD_LEN = 6


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset a FireFleet HQ user's password.",
    )
    parser.add_argument(
        "username",
        nargs="?",
        help="Username whose password should be reset",
    )
    parser.add_argument(
        "-p",
        "--password",
        help="New password (omit to be prompted securely)",
    )
    return parser.parse_args(argv)


def prompt_username() -> str:
    username = input("Enter username: ").strip()
    if not username:
        print("Username is required.", file=sys.stderr)
        sys.exit(1)
    return username


def prompt_password() -> str:
    password = getpass.getpass("Enter new password: ")
    if not password:
        print("Password is required.", file=sys.stderr)
        sys.exit(1)
    confirm = getpass.getpass("Confirm new password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        sys.exit(1)
    return password


def reset_password(username: str, password: str) -> None:
    if len(password) < MIN_PASSWORD_LEN:
        print(
            f"Password must be at least {MIN_PASSWORD_LEN} characters.",
            file=sys.stderr,
        )
        sys.exit(1)

    flask_app = create_app()
    with flask_app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"Error: User '{username}' not found.", file=sys.stderr)
            sys.exit(1)

        user.set_password(password)
        db.session.commit()
        print(f"Password reset for user '{username}'.")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    username = (args.username or "").strip() or prompt_username()
    password = args.password if args.password is not None else prompt_password()
    if not password:
        print("Password is required.", file=sys.stderr)
        sys.exit(1)
    reset_password(username, password)


if __name__ == "__main__":
    main()
