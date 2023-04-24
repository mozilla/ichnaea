#!/usr/bin/env python
"""
Create and drop the db.

Use this only in a local dev environment.
"""

import argparse
import sys

from sqlalchemy.exc import OperationalError, ProgrammingError

from ichnaea.db import create_db, database_is_ready, drop_db, get_sqlalchemy_url


def create_database():
    """Create a database."""
    db_url = get_sqlalchemy_url()
    print("Creating database %s...." % db_url)
    try:
        create_db(uri=db_url)
    except ProgrammingError:
        print("Database already exists.")
        return 1
    print("Done.")


def drop_database():
    """Drop an existing database."""
    db_url = get_sqlalchemy_url()
    print("Dropping database %s...." % db_url)
    drop_db(uri=db_url)
    print("Done.")


def check_database():
    """Check if the database is ready for connections."""
    try:
        database_is_ready()
    except OperationalError as e:
        print(f"Database is not ready: {e}")
        return 1
    else:
        print("Database is ready.")
        return 0


def main(argv):
    parser = argparse.ArgumentParser(description="Work with databases.")
    subparsers = parser.add_subparsers(dest="cmd")
    subparsers.required = True
    subparsers.add_parser("drop", help="drop existing database")
    subparsers.add_parser("create", help="create database")
    subparsers.add_parser("check", help="check if database is accepting connections")

    args = parser.parse_args(argv[1:])

    if args.cmd == "drop":
        return drop_database()
    elif args.cmd == "create":
        return create_database()
    elif args.cmd == "check":
        return check_database()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
