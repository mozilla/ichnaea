"""
Contains helper functionality for reading and parsing configuration files
and parsing of environment variables.
"""
from __future__ import absolute_import

import os
import os.path

from alembic.config import Config as AlembicConfig
from backports.configparser import (
    ConfigParser,
    NoOptionError,
    NoSectionError,
)
import pkg_resources
import simplejson
from six import PY2, string_types

HERE = os.path.dirname(__file__)

RELEASE = None
TESTING = 'TESTING' in os.environ

CONTRIBUTE_FILE = os.path.join(HERE, 'contribute.json')
CONTRIBUTE_INFO = {}
with open(CONTRIBUTE_FILE, 'r') as fd:
    CONTRIBUTE_INFO = simplejson.load(fd)

VERSION = pkg_resources.get_distribution('ichnaea').version
VERSION_FILE = os.path.join(HERE, 'version.json')
VERSION_INFO = {
    'build': None,
    'commit': 'HEAD',
    'source': 'https://github.com/mozilla/ichnaea',
    'tag': 'master',
    'version': VERSION,
}

ASSET_BUCKET = os.environ.get('ASSET_BUCKET')
ASSET_URL = os.environ.get('ASSET_URL')

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
    DB_RO_URI = ('mysql+pymysql://%s:%s@%s:%s/%s' % (
        DB_RO_USER, DB_RO_PWD, DB_RO_HOST, DB_PORT, DB_NAME))

if not DB_RW_URI:
    DB_RW_URI = ('mysql+pymysql://%s:%s@%s:%s/%s' % (
        DB_RW_USER, DB_RW_PWD, DB_RW_HOST, DB_PORT, DB_NAME))

if not DB_DDL_URI:
    DB_DDL_URI = ('mysql+pymysql://%s:%s@%s:%s/%s' % (
        DB_DDL_USER, DB_DDL_PWD, DB_RW_HOST, DB_PORT, DB_NAME))

ALEMBIC_CFG = AlembicConfig()
ALEMBIC_CFG.set_section_option(
    'alembic', 'script_location', os.path.join(HERE, 'alembic'))
ALEMBIC_CFG.set_section_option(
    'alembic', 'sqlalchemy.url', DB_DDL_URI)

GEOIP_PATH = os.environ.get('GEOIP_PATH')
if not GEOIP_PATH:
    GEOIP_PATH = os.path.join(HERE, 'tests/data/GeoIP2-City-Test.mmdb')

ICHNAEA_CFG = os.environ.get('ICHNAEA_CFG')
if not ICHNAEA_CFG:
    ICHNAEA_CFG = os.path.join(HERE, 'tests/data/test.ini')

MAP_ID_BASE = os.environ.get('MAP_ID_BASE')
MAP_ID_LABELS = os.environ.get('MAP_ID_LABELS')
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


class Config(ConfigParser):
    """
    A :class:`configparser.ConfigParser` subclass with added
    functionality.

    :param filename: The path to a configuration file.
    """

    def __init__(self, filename, **kw):
        super(Config, self).__init__(**kw)
        # let's read the file
        if isinstance(filename, string_types):
            self.filename = filename
            self.read(filename)
        else:  # pragma: no cover
            self.filename = None
            self.read_file(filename)

    def get(self, section, option, default=None, **kw):
        """
        A get method which returns the default argument when the option
        cannot be found instead of raising an exception.
        """
        try:
            value = super(Config, self).get(section, option, **kw)
        except (NoOptionError, NoSectionError):  # pragma: no cover
            value = default
        return value

    def get_map(self, section, default=None):
        """
        Return a config section as a dictionary.
        """
        try:
            value = dict(self.items(section))
        except (NoOptionError, NoSectionError):  # pragma: no cover
            value = default
        return value

    def optionxform(self, option):
        """
        Disable automatic lowercasing of option names.
        """
        return option

    def asdict(self):  # pragma: no cover
        """
        Return the entire config as a dict of dicts.
        """
        result = {}
        for section in self.sections():
            result[section] = self.get_map(section)
        return result


class DummyConfig(object):
    """
    A stub implementation of :class:`ichnaea.config.Config` used in tests.

    :param settings: A dict of dicts representing the parsed config
                     settings.
    """

    def __init__(self, settings):
        self.settings = settings

    def get(self, section, option, default=None):  # pragma: no cover
        section_values = self.get_map(section, {})
        return section_values.get(option, default)

    def get_map(self, section, default=None):
        return self.settings.get(section, default)

    def sections(self):
        return list(self.settings.keys())

    def asdict(self):
        result = {}
        for section in self.sections():
            result[section] = self.get_map(section)
        return result


def read_config(filename=ICHNAEA_CFG):
    """
    Read a configuration file from a passed in filename.

    :rtype: :class:`ichnaea.config.Config`
    """
    if PY2 and isinstance(filename, bytes):  # pragma: no cover
        filename = filename.decode('utf-8')

    return Config(filename)
