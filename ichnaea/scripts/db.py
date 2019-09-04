import argparse
import sys

from sqlalchemy.exc import InternalError, ProgrammingError

from ichnaea.db import drop_db, create_db
from ichnaea.conf import DB_DDL_URI


def create_database():
    """Create a database."""
    print("Creating database %s...." % DB_DDL_URI)
    try:
        create_db(uri=DB_DDL_URI)
    except ProgrammingError:
        print("Database already exists.")
        return 1
    print("Done.")


def drop_database():
    """Drop an existing database."""
    print("Dropping database %s...." % DB_DDL_URI)
    try:
        drop_db(uri=DB_DDL_URI)
    except InternalError:
        print("Database does not exist.")
        return 1
    print("Done.")


def main(argv):
    parser = argparse.ArgumentParser(
        description='Create and delete databases.'
    )
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
