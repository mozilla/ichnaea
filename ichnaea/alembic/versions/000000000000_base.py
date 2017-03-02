"""Base schema.

Revision ID: 000000000000
Revises: None
Create Date: 2016-04-14 14:08:27.104535
"""

import logging
import os.path

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '000000000000'
down_revision = None

HERE = os.path.dirname(__file__)
SQL_BASE = os.path.join(HERE, 'base.sql')


def upgrade():
    log.info('Create initial base schema')
    with open(SQL_BASE, 'r') as fd:
        base_sql = fd.read().strip()
    lines = base_sql.split('\n')
    lines = [l for l in lines if not l.startswith('/')]
    stmt = '\n'.join(lines)
    op.execute(sa.text(stmt))
    log.info('Initial schema created.')


def downgrade():
    log.info('Drop initial schema.')
    with open(SQL_BASE, 'r') as fd:
        base_sql = fd.read().strip()
    lines = base_sql.split('\n')
    tables = set()
    for line in lines:
        if 'CREATE TABLE' not in line:
            continue
        name = line.split('`')[1]
        tables.add(name)
    tables = list(tables)
    tables.sort()
    for table in tables:
        stmt = 'DROP TABLE `%s`' % table
        op.execute(sa.text(stmt))
    log.info('Initial schema dropped.')
