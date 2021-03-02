"""
Imported by alembic command to run alembic subcommands.
"""

from alembic import context

from ichnaea.db import configure_db, get_sqlalchemy_url
from ichnaea.log import configure_logging


def run_migrations_online():
    # Create a database connection using SQLALCHEMY_URL defined in the
    # environment.
    db_url = get_sqlalchemy_url()
    db = configure_db(uri=db_url, pool=False)

    with db.engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


configure_logging()
run_migrations_online()
