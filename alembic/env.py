from alembic import context

from ichnaea.db import configure_ddl_db
from ichnaea.log import (
    configure_logging,
)


def run_migrations_online():
    db = configure_ddl_db()
    with db.engine.connect() as connection:
        context.configure(connection=connection)
        with connection.begin() as trans:
            context.run_migrations()
            trans.commit()


configure_logging()
run_migrations_online()
