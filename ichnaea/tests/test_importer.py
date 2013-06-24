import os
from tempfile import mkstemp
from unittest import TestCase

LINE = '9;2;1.23456;-2.3;1;2;3;4;0;0;2013-04-20 02:59:43;2013-04-20 02:59:43;1'


class TestLoadFile(TestCase):

    def _make_one(self):
        from ichnaea.importer import load_file
        tmpfile = mkstemp()
        settings = {'celldb': 'sqlite://'}
        return load_file, settings, tmpfile

    def test_no_lines(self):
        func, settings, tmpfile = self._make_one()
        counter = func(settings, tmpfile[1])
        self.assertEqual(counter, 0)

    def test_one_line(self):
        func, settings, tmpfile = self._make_one()
        os.write(tmpfile[0], LINE)
        counter = func(settings, tmpfile[1])
        self.assertEqual(counter, 1)

    def test_batch(self):
        func, settings, tmpfile = self._make_one()
        os.write(tmpfile[0], LINE)
        os.write(tmpfile[0], '\n1' + LINE)
        os.write(tmpfile[0], '\n2' + LINE)
        counter = func(settings, tmpfile[1], batch_size=2)
        self.assertEqual(counter, 3)

    def test_corrupt_lines(self):
        func, settings, tmpfile = self._make_one()
        os.write(tmpfile[0], LINE + '\n')
        os.write(tmpfile[0], '3;\\N\n')
        os.write(tmpfile[0], '4;\\N;abc\n')
        os.write(tmpfile[0], '5;\\N;1.0;2.1;abc\n')
        counter = func(settings, tmpfile[1])
        self.assertEqual(counter, 1)


class TestMain(TestCase):

    def _make_one(self):
        from ichnaea.importer import main
        config = mkstemp()
        data = mkstemp()
        return config, data, main

    def test_main(self):
        config, data, func = self._make_one()
        os.write(config[0], '[ichnaea]\n')
        os.write(config[0], 'celldb=sqlite://\n')
        os.write(config[0], 'measuredb=sqlite://\n')
        os.write(data[0], LINE)
        counter = func(['main', config[1], data[1]])
        self.assertEqual(counter, 1)
