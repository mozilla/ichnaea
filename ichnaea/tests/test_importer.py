import os
from tempfile import mkstemp
from unittest import TestCase

LINE = '12,1.23456,-2.34,1,2,3,4,0,0,2013-04-20 02:59:43,2013-04-20 02:59:43,1'


class TestImporter(TestCase):

    def _make_one(self):
        from ichnaea.importer import load_file
        tmpfile = mkstemp()
        settings = {'celldb': 'sqlite://'}
        return load_file, settings, tmpfile

    def test_no_lines(self):
        func, settings, tmpfile = self._make_one()
        func(settings, tmpfile[1])

    def test_one_line(self):
        func, settings, tmpfile = self._make_one()
        os.write(tmpfile[0], LINE)
        db = func(settings, tmpfile[1])
        result = db.session().execute('select * from cell;')
        self.assertEqual(result.fetchall(),
            [(12, 1234560, -2340000, 1, 2, 3, 4, 0)])
