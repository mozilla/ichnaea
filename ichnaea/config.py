import os

from configparser import (
    ConfigParser,
    NoOptionError,
    NoSectionError,
)


class Config(ConfigParser):

    def __init__(self, filename):
        ConfigParser.__init__(self)
        # let's read the file
        if isinstance(filename, basestring):
            self.filename = filename
            self.read(filename)
        else:  # pragma: no cover
            self.filename = None
            self.read_file(filename)

    def get(self, section, option, default=None):
        try:
            value = ConfigParser.get(self, section, option)
        except (NoOptionError, NoSectionError):  # pragma: no cover
            value = default
        return value

    def get_map(self, section):
        # Additional convenience API
        return dict(self.items(section))

    def optionxform(self, option):
        # Avoid lower-casing the option names
        return option

    def asdict(self):  # pragma: no cover
        result = {}
        for section in self.sections():
            result[section] = self.get_map(section)
        return result


class DummyConfig(object):

    def __init__(self, settings):
        self.settings = settings

    def get(self, section, option):
        section_values = self.get_map(section)
        return section_values.get(option)

    def get_map(self, section):
        return self.settings.get(section)

    def sections(self):
        return list(self.settings.keys())

    def asdict(self):
        result = {}
        for section in self.sections():
            result[section] = self.get_map(section)
        return result


def read_config(filename=None):
    if filename is None:
        filename = os.environ.get('ICHNAEA_CFG', 'ichnaea.ini')
        filename = filename.decode('utf-8')
    return Config(filename)
