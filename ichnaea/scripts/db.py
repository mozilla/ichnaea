#!/usr/bin/env python
"""
Create and drop the db.

Use this only in a local dev environment.
"""

import argparse
import sys

from sqlalchemy.exc import ProgrammingError

from ichnaea.db import drop_db, create_db, get_sqlalchemy_url


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


def main(argv):
    parser = argparse.ArgumentParser(description="Create and delete databases.")
    subparsers = parser.add_subparsers(dest="cmd")
    subparsers.required = True
    subparsers.add_parser("drop", help="drop existing database")
    subparsers.add_parser("create", help="create database")

    args = parser.parse_args(argv[1:])

    if args.cmd == "drop":
        return drop_database()
    elif args.cmd == "create":
        return create_database()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
