import os
from tempfile import mkstemp

from ichnaea.tests.base import (
    CeleryTestCase,
    SQLURI,
    SQLSOCKET,
)

LINE = (
    "1376952704\td5ee506df32b8d71d78f37133eaaaf137385847e\t"
    "37.871930\t-122.273156\t-16\t11\tdc:45:17:75:8f:80\tATT560"
)


class TestLoadFile(CeleryTestCase):

    def _make_one(self):
        from ichnaea.importer import load_file
        tmpfile = mkstemp()
        return load_file, tmpfile

    def test_no_lines(self):
        func, tmpfile = self._make_one()
        counter = func(self.db_master_session, tmpfile[1])
        self.assertEqual(counter, 0)

    def test_one_line(self):
        func, tmpfile = self._make_one()
        os.write(tmpfile[0], LINE)
        counter = func(self.db_master_session, tmpfile[1])
        self.assertEqual(counter, 1)

    def test_batch(self):
        func, tmpfile = self._make_one()
        os.write(tmpfile[0], LINE)
        os.write(tmpfile[0], '\n1' + LINE)
        os.write(tmpfile[0], '\n2' + LINE)
        counter = func(self.db_master_session, tmpfile[1], batch_size=2)
        self.assertEqual(counter, 3)

    def test_corrupt_lines(self):
        func, tmpfile = self._make_one()
        os.write(tmpfile[0], LINE + '\n')
        os.write(tmpfile[0], '3\t\\N\n')
        os.write(tmpfile[0], '4\t\\N\tabc\n')
        os.write(tmpfile[0], '5\t\\N\t1.0\t2.1\tabc\n')
        counter = func(self.db_master_session, tmpfile[1])
        self.assertEqual(counter, 1)


class TestMain(CeleryTestCase):

    def _make_one(self):
        from ichnaea.importer import main
        config = mkstemp()
        data = mkstemp()
        return config, data, main

    def test_main(self):
        config, data, func = self._make_one()
        os.write(config[0], '[ichnaea]\n')
        os.write(config[0], 'db_master=%s\n' % SQLURI)
        os.write(config[0], 'db_master_socket=%s\n' % SQLSOCKET)
        counter = func(['main', '--dry-run', config[1], data[1]])
        self.assertEqual(counter, 0)
