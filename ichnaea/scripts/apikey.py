#!/usr/bin/env python
"""
Create and manipulate API keys.
"""

import argparse
import uuid
import sys

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.exc import IntegrityError

from ichnaea.api.key import API_KEY_COLUMN_NAMES, Key
from ichnaea.models.api import ApiKey
from ichnaea.db import configure_db, db_worker_session
from ichnaea.util import print_table


def create_api_key(key):
    """Create a new api key."""
    key = key or str(uuid.uuid4())

    db = configure_db("rw")
    with db_worker_session(db) as session:
        try:
            session.execute(
                insert(ApiKey.__table__).values(
                    valid_key=key,
                    allow_fallback=False,
                    allow_locate=True,
                    allow_region=True,
                    store_sample_locate=100,
                    store_sample_submit=100,
                )
            )
            print("Created API key: %r" % key)
        except IntegrityError:
            print("API key %r exists" % key)


def list_api_keys():
    """List all api keys in db."""
    show_fields = ["valid_key", "allow_fallback", "allow_locate", "allow_region"]

    db = configure_db("rw")
    with db_worker_session(db) as session:
        columns = ApiKey.__table__.columns
        fields = [getattr(columns, f) for f in show_fields]
        rows = session.execute(select(fields)).fetchall()

    print("%d api keys." % len(rows))
    if rows:
        # Add header row
        table = [show_fields]
        # Add rest of the rows; the columns are in the order of show_fields so we
        # don't have to do any re-ordering
        table.extend(rows)
        print_table(table)


def show_api_key_details(key):
    """Print api key details to stdout."""
    db = configure_db("rw")
    with db_worker_session(db) as session:
        columns = ApiKey.__table__.columns
        fields = [getattr(columns, f) for f in API_KEY_COLUMN_NAMES]
        row = (
            session.execute(select(fields).where(columns.valid_key == key))
        ).fetchone()
        if row is not None:
            key = Key(**dict(row.items()))
        else:
            key = None
    table = []
    for field in API_KEY_COLUMN_NAMES:
        table.append([field, getattr(key, field, "")])

    print_table(table, " : ")


def main(argv):
    parser = argparse.ArgumentParser(description="Manipulate API keys.")
    subparsers = parser.add_subparsers(dest="cmd")
    subparsers.required = True

    subparsers.add_parser("list", help="list api keys")
    create_parser = subparsers.add_parser("create", help="create new api key")
    create_parser.add_argument(
        "key", nargs="?", help="the api key; defaults to a uuid4"
    )

    show_parser = subparsers.add_parser("show", help="show details for an api key")
    show_parser.add_argument("key", help="the key to show details for")

    args = parser.parse_args(argv[1:])

    if args.cmd == "create":
        return create_api_key(args.key)
    if args.cmd == "show":
        return show_api_key_details(args.key)
    if args.cmd == "list":
        return list_api_keys()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
