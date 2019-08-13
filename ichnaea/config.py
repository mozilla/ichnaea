"""
Contains helper functionality for parsing environment variables.
"""
from __future__ import absolute_import

import json
import os
import os.path

from alembic.config import Config as AlembicConfig
import simplejson

HERE = os.path.dirname(__file__)

RELEASE = None
TESTING = 'TESTING' in os.environ

CONTRIBUTE_FILE = os.path.join(HERE, 'contribute.json')
CONTRIBUTE_INFO = {}
with open(CONTRIBUTE_FILE, 'r') as fd:
    CONTRIBUTE_INFO = simplejson.load(fd)


VERSION_INFO = {}
VERSION_FILE = os.path.join(HERE, 'version.json')
if os.path.exists(VERSION_FILE):
    with open(VERSION_FILE, "r") as fp:
        try:
            VERSION_INFO = json.load(fp)
        except json.JsonDecodeException:
            pass

ASSET_BUCKET = os.environ.get('ASSET_BUCKET')
ASSET_URL = os.environ.get('ASSET_URL')

# One of pymysql or mysqlconnector
DB_LIBRARY = os.environ.get('DB_LIBRARY', 'pymysql')

DB_HOST = os.environ.get('DB_HOST')
DB_RO_HOST = os.environ.get('DB_RO_HOST', DB_HOST)
DB_RW_HOST = os.environ.get('DB_RW_HOST', DB_HOST)

DB_USER = os.environ.get('DB_USER', 'location')
DB_RO_USER = os.environ.get('DB_RO_USER', DB_USER)
DB_RW_USER = os.environ.get('DB_RW_USER', DB_USER)
DB_DDL_USER = os.environ.get('DB_DDL_USER', DB_USER)

DB_PWD = os.environ.get('DB_PWD', 'location')
DB_RO_PWD = os.environ.get('DB_RO_PWD', DB_PWD)
DB_RW_PWD = os.environ.get('DB_RW_PWD', DB_PWD)
DB_DDL_PWD = os.environ.get('DB_DDL_PWD', DB_PWD)

DB_PORT = os.environ.get('DB_PORT', '3306')
DB_NAME = os.environ.get('DB_NAME', 'location')

DB_RW_URI = os.environ.get('DB_RW_URI')
DB_RO_URI = os.environ.get('DB_RO_URI')
DB_DDL_URI = os.environ.get('DB_DDL_URI')

if not DB_RO_URI:
    DB_RO_URI = ('mysql+%s://%s:%s@%s:%s/%s' % (
        DB_LIBRARY, DB_RO_USER, DB_RO_PWD, DB_RO_HOST, DB_PORT, DB_NAME))

if not DB_RW_URI:
    DB_RW_URI = ('mysql+%s://%s:%s@%s:%s/%s' % (
        DB_LIBRARY, DB_RW_USER, DB_RW_PWD, DB_RW_HOST, DB_PORT, DB_NAME))

if not DB_DDL_URI:
    DB_DDL_URI = ('mysql+%s://%s:%s@%s:%s/%s' % (
        DB_LIBRARY, DB_DDL_USER, DB_DDL_PWD, DB_RW_HOST, DB_PORT, DB_NAME))

ALEMBIC_CFG = AlembicConfig()
ALEMBIC_CFG.set_section_option(
    'alembic', 'script_location', os.path.join(HERE, 'alembic'))
ALEMBIC_CFG.set_section_option(
    'alembic', 'sqlalchemy.url', DB_DDL_URI)

GEOIP_PATH = os.environ.get('GEOIP_PATH')
if not GEOIP_PATH:
    GEOIP_PATH = os.path.join(HERE, 'tests/data/GeoIP2-City-Test.mmdb')

MAP_TOKEN = os.environ.get('MAP_TOKEN')

REDIS_HOST = os.environ.get('REDIS_HOST')
REDIS_PORT = os.environ.get('REDIS_PORT', '6379')
REDIS_DB = '1' if TESTING else '0'
REDIS_URI = os.environ.get('REDIS_URI')
if REDIS_HOST and not REDIS_URI:
    REDIS_URI = 'redis://%s:%s/%s' % (REDIS_HOST, REDIS_PORT, REDIS_DB)

SENTRY_DSN = os.environ.get('SENTRY_DSN')
STATSD_HOST = os.environ.get('STATSD_HOST')

if os.path.isfile(VERSION_FILE):
    with open(VERSION_FILE, 'r') as fd:
        data = simplejson.load(fd)
    VERSION_INFO['build'] = data.get('build', None)
    VERSION_INFO['commit'] = data.get('commit', None)
    VERSION_INFO['tag'] = RELEASE = data.get('tag', None)
