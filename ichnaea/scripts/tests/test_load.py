from ichnaea.scripts import load


class TestLoad(object):

    def test_compiles(self):
        assert hasattr(load, 'console_entry')
