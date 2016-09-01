import os.path

from alembic import command as alembic_command
from alembic.autogenerate import compare_metadata
from alembic.ddl.impl import _type_comparators
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy.schema import MetaData
from sqlalchemy.sql import sqltypes

from ichnaea.conftest import (
    ALEMBIC_CFG,
    cleanup_tables,
    setup_database,
)
# make sure all models are imported
from ichnaea.models import _Model  # NOQA

from ichnaea.tests import DATA_DIRECTORY

_compare_attrs = {
    sqltypes._Binary: ('length', ),
    sqltypes.Date: (),
    sqltypes.DateTime: ('fsp', 'timezone'),
    sqltypes.Integer: ('display_width', 'unsigned', 'zerofill'),
    sqltypes.String: ('binary', 'charset', 'collation', 'length', 'unicode'),
}

SQL_BASE = os.path.join(DATA_DIRECTORY, 'base.sql')


def db_compare_type(context, inspected_column,
                    metadata_column, inspected_type, metadata_type):
    # return True if the types are different, False if not, or None
    # to allow the default implementation to compare these types
    expected = metadata_column.type
    migrated = inspected_column.type

    # this extends the logic in alembic.ddl.impl.DefaultImpl.compare_type
    type_affinity = migrated._type_affinity
    compare_attrs = _compare_attrs.get(type_affinity, None)
    if compare_attrs is not None:
        if type(expected) != type(migrated):
            return True
        for attr in compare_attrs:
            if getattr(expected, attr, None) != getattr(migrated, attr, None):
                return True
        return False

    # fall back to limited alembic type comparison
    comparator = _type_comparators.get(type_affinity, None)
    if comparator is not None:
        return comparator(expected, migrated)
    raise AssertionError('Unsupported DB type comparison.')


class TestMigration(object):

    @pytest.fixture(scope='function')
    def db(self, db_rw):
        yield db_rw
        # setup normal database schema again
        setup_database()

    def current_db_revision(self, db):
        with db.engine.connect() as conn:
            result = conn.execute('select version_num from alembic_version')
            alembic_rev = result.first()
        return None if alembic_rev is None else alembic_rev[0]

    def test_migration(self, db):
        # capture state of fresh database
        metadata = MetaData()
        metadata.reflect(bind=db.engine)

        # drop all tables
        cleanup_tables(db.engine)

        # setup old database schema
        with open(SQL_BASE) as fd:
            sql_text = fd.read()
        with db.engine.connect() as conn:
            conn.execute(sql_text)

        # we have no alembic base revision
        assert self.current_db_revision(db) is None

        # run the migration
        with db.engine.connect() as conn:
            alembic_command.upgrade(ALEMBIC_CFG, 'head')

        # afterwards the DB is stamped
        db_revision = self.current_db_revision(db)
        assert db_revision is not None

        # db revision matches latest alembic revision
        alembic_script = ScriptDirectory.from_config(ALEMBIC_CFG)
        alembic_head = alembic_script.get_current_head()
        assert db_revision == alembic_head

        # compare the db schema from a migrated database to
        # one created fresh from the model definitions
        opts = {
            'compare_type': db_compare_type,
            'compare_server_default': True,
        }
        with db.engine.connect() as conn:
            context = MigrationContext.configure(connection=conn, opts=opts)
            metadata_diff = compare_metadata(context, metadata)

        assert metadata_diff == []
