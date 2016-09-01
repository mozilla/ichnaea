"""remove user/score tables

Revision ID: 4255b858a37e
Revises: 27400b0c8b42
Create Date: 2016-04-12 10:56:36.512919
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '4255b858a37e'
down_revision = '27400b0c8b42'


def upgrade():
    log.info('Drop score table.')
    stmt = 'DROP TABLE score'
    op.execute(sa.text(stmt))

    log.info('Drop user table.')
    stmt = 'DROP TABLE user'
    op.execute(sa.text(stmt))


def downgrade():
    log.info('Recreate user table.')
    stmt = '''\
CREATE TABLE `user` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `nickname` varchar(128) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_nickname_unique` (`nickname`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
'''
    op.execute(sa.text(stmt))

    log.info('Recreate score table.')
    stmt = '''\
CREATE TABLE `score` (
  `userid` int(10) unsigned NOT NULL,
  `key` tinyint(4) NOT NULL,
  `time` date NOT NULL,
  `value` int(11) DEFAULT NULL,
  PRIMARY KEY (`key`,`userid`,`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
'''
    op.execute(sa.text(stmt))
