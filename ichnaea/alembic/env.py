from alembic import context

from ichnaea.db import configure_db
from ichnaea.log import configure_logging


def run_migrations_online():
    db = configure_db("ddl")
    with db.engine.connect() as connection:
        context.configure(connection=connection)
        with connection.begin() as trans:
            context.run_migrations()
            trans.commit()


configure_logging()
run_migrations_online()
