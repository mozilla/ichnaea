import os
import pathlib

from alembic import command as alembic_command
from alembic.autogenerate import compare_metadata
from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.schema import MetaData

from ichnaea.conftest import cleanup_tables

# make sure all models are imported
from ichnaea.models import _Model  # noqa


def compare_schema(engine, metadata):
    # compare the db schema from a migrated database to
    # one created fresh from the model definitions
    opts = {"compare_type": True, "compare_server_default": True}
    with engine.connect() as conn:
        context = MigrationContext.configure(connection=conn, opts=opts)
        diff = compare_metadata(context, metadata)
    return diff


def current_db_revision(db):
    with db.engine.connect() as conn:
        result = conn.execute("select version_num from alembic_version")
        alembic_rev = result.first()
    return None if alembic_rev is None else alembic_rev[0]


def get_alembic_config():
    """Returns an alembic Config with the right ini file."""
    # alembic.ini is in the repository root.
    alembic_ini = str(pathlib.Path(__file__).parent.parent.parent / "alembic.ini")
    assert os.path.exists(alembic_ini)
    return AlembicConfig(alembic_ini)


class TestMigration(object):
    def test_migration(self, clean_db):
        # To create a new base.sql, run mysqldump.
        # $ docker-compose exec mysql bash
        # $$ mysqldump -ulocation -plocation -d --compact location
        db = clean_db

        # The DB is stamped
        db_revision = current_db_revision(db)
        assert db_revision is not None

        alembic_cfg = get_alembic_config()

        # db revision matches latest alembic revision
        alembic_script = ScriptDirectory.from_config(alembic_cfg)
        alembic_head = alembic_script.get_current_head()
        assert db_revision == alembic_head

        # capture state of a fresh database
        fresh_metadata = MetaData()
        fresh_metadata.reflect(bind=db.engine)

        # downgrade back to the beginning
        with db.engine.connect() as conn:
            with conn.begin() as trans:
                alembic_command.downgrade(alembic_cfg, "base")
                trans.commit()

        # capture state of a downgraded database
        downgraded_metadata = MetaData()
        downgraded_metadata.reflect(bind=db.engine)

        # drop all tables
        cleanup_tables(db.engine)

        # capture state of an empty database
        empty_metadata = MetaData()
        empty_metadata.reflect(bind=db.engine)

        # compare the db schema from a downgraded database to
        # an empty one
        assert compare_schema(db.engine, empty_metadata) == []

        # Set up schema based on model definitions.
        with db.engine.connect() as conn:
            with conn.begin() as trans:
                _Model.metadata.create_all(db.engine)
                trans.commit()

        # capture state of a model database
        model_metadata = MetaData()
        model_metadata.reflect(bind=db.engine)

        # compare the db schema from a fresh database to
        # one created from the model definitions
        assert compare_schema(db.engine, fresh_metadata) == []
