import os
from tempfile import mkstemp

from ichnaea.content.models import (
    MapStat,
    MAPSTAT_TYPE,
    Score,
    SCORE_TYPE_INVERSE,
    User,
)
from ichnaea.tests.base import CeleryTestCase

LINE = (
    "1376952704\t37.871930\t-122.273156\t-16\t11\tdc:45:17:75:8f:80\tATT560"
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

    def test_userid(self):
        func, tmpfile = self._make_one()
        session = self.db_master_session
        user = User(nickname='test')
        session.add(user)
        session.flush()
        userid = user.id
        os.write(tmpfile[0], LINE)
        os.write(tmpfile[0], '\n1' + LINE)
        os.write(tmpfile[0], '\n2' + LINE)
        counter = func(session, tmpfile[1], batch_size=2, userid=userid)
        self.assertEqual(counter, 3)
        # test user scores and mapstat
        scores = session.query(Score).filter(Score.userid == userid).all()
        scores = dict([(SCORE_TYPE_INVERSE[s.key], s.value) for s in scores])
        self.assertEqual(
            scores, {'new_location': 1, 'new_wifi': 1, 'location': 3})
        mapstats = session.query(MapStat).filter(
            MapStat.key == MAPSTAT_TYPE['location']).all()
        mapstats = [(m.lat, m.lon, m.value) for m in mapstats]
        self.assertEqual(mapstats, [(378719, -1222732, 3)])

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
        data = mkstemp()
        return data, main

    def test_main(self):
        data, func = self._make_one()
        counter = func(['main', data[1]], _db_master=self.db_master)
        self.assertEqual(counter, 0)

    def test_main_userid(self):
        data, func = self._make_one()
        counter = func(['main', data[1], '--userid=1'],
                       _db_master=self.db_master)
        self.assertEqual(counter, 0)
