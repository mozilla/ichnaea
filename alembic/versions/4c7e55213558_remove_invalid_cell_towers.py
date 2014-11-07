"""Remove invalid cell towers

Revision ID: 4c7e55213558
Revises: 5214b5cfc5d2
Create Date: 2014-11-10 02:16:42.059200

"""

# revision identifiers, used by Alembic.
revision = '4c7e55213558'
down_revision = '5214b5cfc5d2'

from alembic import op


def upgrade():
    bind = op.get_bind()

    # deleted_rows = delete from cell where radio != 1 and mnc >= 1000
    stmt = 'DELETE FROM cell WHERE radio != 1 AND mnc >= 1000'
    result = bind.execute(stmt)
    deleted = result.rowcount

    # delete from cell_blacklist where radio != 1 and mnc >= 1000
    stmt = 'DELETE FROM cell_blacklist WHERE radio != 1 AND mnc >= 1000'
    bind.execute(stmt)

    # max_date = select max(time) from stat where `key` = 2
    stmt = 'SELECT max(time) FROM stat WHERE `key` = 2'
    max_date = bind.execute(stmt).fetchone()[0]

    # update stat set value = value - <deleted_rows>
    # where `key` = 2 and time = <max_date>
    stmt = ('UPDATE stat SET value = value - {deleted} '
            'WHERE `key` = 2 AND `time` = \'{max_date}\'').format(
                deleted=deleted,
                max_date=max_date.strftime('%Y-%m-%d'))
    bind.execute(stmt)


def downgrade():
    pass
