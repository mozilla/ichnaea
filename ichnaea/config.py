"""
Contains helper functionality for reading and parsing configuration files.
"""

import os

from configparser import (
    ConfigParser,
    NoOptionError,
    NoSectionError,
)
from six import PY2, string_types


class Config(ConfigParser):
    """
    A :class:`configparser.ConfigParser` subclass with added
    functionality.

    :param filename: The path to a configuration file.
    """

    def __init__(self, filename):
        ConfigParser.__init__(self)
        # let's read the file
        if isinstance(filename, string_types):
            self.filename = filename
            self.read(filename)
        else:  # pragma: no cover
            self.filename = None
            self.read_file(filename)

    def get(self, section, option, default=None):
        """
        A get method which returns the default argument when the option
        cannot be found instead of raising an exception.
        """
        try:
            value = ConfigParser.get(self, section, option)
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

    def get(self, section, option, default=None):
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


def read_config(filename=None, envvar='ICHNAEA_CFG', fallback='location.ini'):
    """
    Read a configuration file from three possible locations:

    1. from the passed in filename,
    2. from the environment variable passed as `envvar`
    3. from the `fallback` file in the current working directory.

    :rtype: :class:`ichnaea.config.Config`
    """
    if filename is None:
        filename = os.environ.get(envvar, fallback)
        if PY2:  # pragma: no cover
            filename = filename.decode('utf-8')
    return Config(filename)
