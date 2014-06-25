from configparser import ConfigParser


class Config(ConfigParser):

    def __init__(self, filename):
        ConfigParser.__init__(self)
        # let's read the file
        if isinstance(filename, basestring):
            self.filename = filename
            self.read(filename)
        else:
            self.filename = None
            self.read_file(filename)

    def get_map(self, section):
        # Additional convenience API
        return dict(self.items(section))

    def optionxform(self, option):
        # Avoid lower-casing the option names
        return option
