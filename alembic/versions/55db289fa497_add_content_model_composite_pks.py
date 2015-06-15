"""add content model composite pks

Revision ID: 55db289fa497
Revises: 14dbafc4fec2
Create Date: 2015-06-15 12:20:10.273609
"""

import logging

from alembic import op
import sqlalchemy as sa

log = logging.getLogger('alembic.migration')
revision = '55db289fa497'
down_revision = '14dbafc4fec2'


def upgrade():
    # all the not null changes are to combat MySQL implicitly inserting
    # 'default 0' for new primary key columns
    log.info('Altering stat table')
    stmt = ("ALTER TABLE stat "
            "DROP PRIMARY KEY, "
            "CHANGE COLUMN `id` `id` int(10) unsigned, "
            "CHANGE COLUMN `key` `key` tinyint(4) NOT NULL, "
            "CHANGE COLUMN `time` `time` date NOT NULL, "
            "ADD PRIMARY KEY(`key`, `time`), "
            "DROP INDEX stat_key_time_unique")
    op.execute(sa.text(stmt))

    log.info('Altering score table')
    stmt = ("ALTER TABLE score "
            "DROP PRIMARY KEY, "
            "CHANGE COLUMN `id` `id` int(10) unsigned, "
            "CHANGE COLUMN `userid` `userid` int(10) unsigned NOT NULL, "
            "CHANGE COLUMN `key` `key` tinyint(4) NOT NULL, "
            "CHANGE COLUMN `time` `time` date NOT NULL, "
            "ADD PRIMARY KEY(`key`, `userid`, `time`), "
            "DROP INDEX score_userid_key_time_unique, "
            "DROP INDEX ix_score_userid")
    op.execute(sa.text(stmt))


def downgrade():
    pass
