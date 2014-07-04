"""Extend mapstat table

Revision ID: 23a8a4ccc96f
Revises: 45059acb751f
Create Date: 2014-07-04 09:31:23.655496

"""

# revision identifiers, used by Alembic.
revision = '23a8a4ccc96f'
down_revision = '45059acb751f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    stmt = "RENAME table mapstat to mapstat_old"
    op.execute(sa.text(stmt))

    stmt = """\
CREATE TABLE `mapstat` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `time` date DEFAULT NULL,
  `lat` int(11) DEFAULT NULL,
  `lon` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `mapstat_lat_lon_unique` (`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
"""
    op.execute(sa.text(stmt))

    stmt = """\
INSERT INTO mapstat (time, lat, lon)
(SELECT date(now()) as today, lat, lon FROM mapstat_old)
"""
    op.execute(sa.text(stmt))

    op.drop_table('mapstat_old')


def downgrade():
    stmt = "RENAME table mapstat to mapstat_new"
    op.execute(sa.text(stmt))

    stmt = """\
CREATE TABLE `mapstat` (
  `lat` int(11) NOT NULL,
  `lon` int(11) NOT NULL,
  `key` smallint(6) NOT NULL,
  `value` int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (`key`,`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
"""
    op.execute(sa.text(stmt))

    stmt = """\
INSERT INTO mapstat (SELECT lat, lon, 2, 1 FROM mapstat_old)
"""
    op.execute(sa.text(stmt))

    op.drop_table('mapstat_new')
