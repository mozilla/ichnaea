#!/usr/bin/env python
"""
Create and manipulate API keys.
"""

import functools
import uuid

import click
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.exc import IntegrityError

from ichnaea.api.key import Key
from ichnaea.models.api import ApiKey
from ichnaea.db import configure_db, db_worker_session
from ichnaea.util import print_table


click_echo_no_nl = functools.partial(click.echo, nl=False)


@click.group()
def apikey_group():
    pass


@apikey_group.command("create")
@click.option("--maxreq", default=100, help="Rate limit for requests")
@click.argument("key", default="")
@click.pass_context
def create_api_key(ctx, maxreq, key):
    """Create a new api key.

    If KEY is not specified, it uses a uuid4.

    """
    key = key or str(uuid.uuid4())

    db = configure_db("rw")
    with db_worker_session(db) as session:
        try:
            session.execute(
                insert(ApiKey.__table__).values(
                    valid_key=key,
                    maxreq=maxreq,
                    allow_fallback=False,
                    allow_locate=True,
                    allow_region=True,
                    store_sample_locate=100,
                    store_sample_submit=100,
                )
            )
            click.echo("Created API key: %r" % key)
        except IntegrityError:
            click.echo("API key %r exists" % key)


@apikey_group.command("list")
@click.pass_context
def list_api_keys(ctx):
    """List all api keys in db."""
    show_fields = ["valid_key", "allow_fallback", "allow_locate", "allow_region"]

    db = configure_db("rw")
    with db_worker_session(db) as session:
        columns = ApiKey.__table__.columns
        fields = [getattr(columns, f) for f in show_fields]
        rows = session.execute(select(fields)).fetchall()

    click.echo("%d api keys." % len(rows))
    if rows:
        # Add header row
        table = [show_fields]
        # Add rest of the rows; the columns are in the order of show_fields so we
        # don't have to do any re-ordering
        table.extend(rows)
        print_table(table, stream_write=click_echo_no_nl)


@apikey_group.command("show")
@click.argument("key")
@click.pass_context
def show_api_key_details(ctx, key):
    """Print api key details to stdout."""
    db = configure_db("rw")
    with db_worker_session(db) as session:
        row = session.query(ApiKey).filter(ApiKey.valid_key == key).one_or_none()
        if row:
            api_key = Key.from_obj(row)
        else:
            api_key = None

    if api_key:
        table = [[name, value] for name, value in api_key.as_dict().items()]
        print_table(table, delimiter=" : ", stream_write=click_echo_no_nl)
    else:
        click.echo(f"API key '{key}' does not exist")


if __name__ == "__main__":
    apikey_group()
