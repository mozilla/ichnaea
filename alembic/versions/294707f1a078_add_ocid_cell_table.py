"""add ocid cell table

Revision ID: 294707f1a078
Revises: 5aa7d2b976eb
Create Date: 2014-08-26 09:39:54.776904

"""

# revision identifiers, used by Alembic.
revision = '294707f1a078'
down_revision = '5aa7d2b976eb'

from alembic import op
import sqlalchemy as sa


def upgrade():

    stmt = """\
CREATE TABLE `ocid_cell` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `radio` tinyint(4) DEFAULT NULL,
  `mcc` smallint(6) DEFAULT NULL,
  `mnc` smallint(6) DEFAULT NULL,
  `lac` int(11) DEFAULT NULL,
  `cid` int(11) DEFAULT NULL,
  `psc` smallint(6) DEFAULT NULL,
  `range` int(11) DEFAULT NULL,
  `total_measures` int(10) unsigned DEFAULT NULL,
  `changeable` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ocid_cell_idx_unique` (`radio`,`mcc`,`mnc`,`lac`,`cid`),
  KEY `ocid_cell_created_idx` (`created`)
) ENGINE=InnoDB AUTO_INCREMENT=34 DEFAULT CHARSET=utf8
"""
    op.execute(sa.text(stmt))


def downgrade():
    op.drop_table('ocid_cell')
