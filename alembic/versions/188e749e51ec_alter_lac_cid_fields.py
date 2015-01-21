"""alter lac cid fields

Revision ID: 188e749e51ec
Revises: 1a116bcd0851
Create Date: 2014-12-19 20:09:59.508290

"""

# revision identifiers, used by Alembic.
revision = '188e749e51ec'
down_revision = '1a116bcd0851'

import logging

from alembic import op

log = logging.getLogger('alembic.migration')


def upgrade():
    log.info('Running cell update')
    op.execute('UPDATE cell SET lac = 0 WHERE lac < 0')
    op.execute('UPDATE cell SET cid = 0 WHERE cid < 0')

    log.info('Running cell_blacklist update')
    op.execute('UPDATE cell_blacklist SET lac = 0 WHERE lac < 0')
    op.execute('UPDATE cell_blacklist SET cid = 0 WHERE cid < 0')

    log.info('Running cell_measure update')
    op.execute('UPDATE cell_measure SET lac = 0, cid = 0 '
               'WHERE lac < 0 and cid < 0')
    op.execute('UPDATE cell_measure SET lac = 0 WHERE lac < 0')
    op.execute('UPDATE cell_measure SET cid = 0 WHERE cid < 0')

    log.info('Altering cell table')
    op.execute('ALTER TABLE cell '
               'MODIFY lac SMALLINT UNSIGNED DEFAULT NULL, '
               'MODIFY cid INT UNSIGNED DEFAULT NULL')

    log.info('Altering cell_blacklist table')
    op.execute('ALTER TABLE cell_blacklist '
               'MODIFY lac SMALLINT UNSIGNED DEFAULT NULL, '
               'MODIFY cid INT UNSIGNED DEFAULT NULL')

    log.info('Altering cell_measure table')
    op.execute('ALTER TABLE cell_measure '
               'MODIFY lac SMALLINT UNSIGNED DEFAULT NULL, '
               'MODIFY cid INT UNSIGNED DEFAULT NULL')


def downgrade():
    op.execute('ALTER TABLE cell '
               'MODIFY lac INT SIGNED DEFAULT NULL, '
               'MODIFY cid INT SIGNED DEFAULT NULL')

    op.execute('ALTER TABLE cell_blacklist '
               'MODIFY lac INT SIGNED DEFAULT NULL, '
               'MODIFY cid INT SIGNED DEFAULT NULL')

    op.execute('ALTER TABLE cell_measure '
               'MODIFY lac INT SIGNED DEFAULT NULL, '
               'MODIFY cid INT SIGNED DEFAULT NULL')

    op.execute('UPDATE cell SET lac = -1 WHERE lac = 0')
    op.execute('UPDATE cell SET cid = -1 WHERE cid = 0')

    op.execute('UPDATE cell_blacklist SET lac = -1 WHERE lac = 0')
    op.execute('UPDATE cell_blacklist SET cid = -1 WHERE cid = 0')

    op.execute('UPDATE cell_measure SET lac = -1 WHERE lac = 0')
    op.execute('UPDATE cell_measure SET cid = -1 WHERE cid = 0')
