"""remove invalid lac values

Revision ID: 10542c592089
Revises: fe2cfea89f5
Create Date: 2015-01-26 23:02:29.321274

"""

# revision identifiers, used by Alembic.
revision = '10542c592089'
down_revision = 'fe2cfea89f5'

from alembic import op

from ichnaea.models import RADIO_TYPE
from ichnaea.content.models import STAT_TYPE


def upgrade():
    # correct the unique cell statistic
    bind = op.get_bind()

    gsm_family = (RADIO_TYPE['gsm'], RADIO_TYPE['umts'], RADIO_TYPE['lte'])

    for table, stat in (
            ('cell', STAT_TYPE['unique_cell']),
            ('ocid_cell', STAT_TYPE['unique_ocid_cell'])):
        stmt = 'SELECT max(time) FROM stat WHERE `key` = {stat}'.format(
            stat=stat)
        max_date = bind.execute(stmt).fetchone()[0]

        if not max_date:
            continue
        max_date = max_date.strftime('%Y-%m-%d')

        stmt = ('SELECT count(*) FROM {table} WHERE '
                '(lac = 65535 OR (lac = 65534 AND radio IN {radios})) '
                'AND created < \'{max_date}\'').format(
                    table=table, radios=gsm_family, max_date=max_date)
        cell_count = bind.execute(stmt).fetchone()[0]

        stmt = ('UPDATE stat SET `value` = `value` - {count} '
                'WHERE `key` = {stat} AND `time` = \'{max_date}\'').format(
                    count=cell_count, stat=stat, max_date=max_date)
        bind.execute(stmt)

    for table in (
            'cell', 'cell_blacklist', 'cell_area',
            'ocid_cell', 'ocid_cell_area'):
        stmt = ('DELETE FROM {table} WHERE lac = 65535 OR '
                '(lac = 65534 AND radio IN {radios})').format(
                    table=table, radios=gsm_family)
        bind.execute(stmt)


def downgrade():
    pass
