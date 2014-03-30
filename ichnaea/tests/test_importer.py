import os
from datetime import datetime
from tempfile import mkstemp

from ichnaea.models import (
    WifiMeasure,
)

from ichnaea.content.models import (
    MapStat,
    MAPSTAT_TYPE,
    Score,
    SCORE_TYPE_INVERSE,
    User,
)
from ichnaea.tests.base import CeleryTestCase

LINE = ("1376952704\tdc:45:17:75:8f:80\t37.871930\t-122.273156\t"
        "5\t500\t0\t11\t-16\tATT560")


class TestLoadFile(CeleryTestCase):

    def _make_one(self):
        from ichnaea.importer import load_file
        tmpfile = mkstemp()
        return load_file, tmpfile

    def test_no_lines(self):
        func, tmpfile = self._make_one()
        counter = func(self.archival_db_session,
                       self.volatile_db_session,
                       tmpfile[1])
        self.assertEqual(counter, 0)

    def test_one_line(self):
        func, tmpfile = self._make_one()
        a_session = self.archival_db_session
        today = datetime.utcnow().date()

        os.write(tmpfile[0], LINE)
        counter = func(a_session, self.volatile_db_session, tmpfile[1])
        self.assertEqual(counter, 1)

        measures = a_session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 1)
        measure = measures[0]
        self.assertEqual(measure.lat, 378719300)
        self.assertEqual(measure.lon, -1222731560)
        self.assertEqual(measure.key, 'dc4517758f80')
        self.assertEqual(measure.channel, 11)
        self.assertEqual(measure.signal, -16)
        self.assertEqual(measure.accuracy, 5)
        self.assertEqual(measure.altitude, 500)
        self.assertEqual(measure.altitude_accuracy, 0)
        self.assertEqual(measure.created.date(), today)
        self.assertEqual(measure.time.date(), today.replace(day=1))

    def test_batch(self):
        func, tmpfile = self._make_one()
        os.write(tmpfile[0], LINE)
        os.write(tmpfile[0], '\n1' + LINE)
        os.write(tmpfile[0], '\n2' + LINE)
        counter = func(self.archival_db_session,
                       self.volatile_db_session,
                       tmpfile[1], batch_size=2)
        self.assertEqual(counter, 3)

    def test_userid(self):
        func, tmpfile = self._make_one()
        a_session = self.archival_db_session
        v_session = self.volatile_db_session
        user = User(nickname='test'.decode('ascii'))
        v_session.add(user)
        v_session.flush()
        userid = user.id
        os.write(tmpfile[0], LINE)
        os.write(tmpfile[0], '\n1' + LINE)
        os.write(tmpfile[0], '\n2' + LINE)
        counter = func(a_session, v_session, tmpfile[1],
                       batch_size=2, userid=userid)
        self.assertEqual(counter, 3)
        # test user scores and mapstat
        scores = v_session.query(Score).filter(Score.userid == userid).all()
        scores = dict([(SCORE_TYPE_INVERSE[s.key], s.value) for s in scores])
        self.assertEqual(
            scores, {'new_location': 1, 'new_wifi': 1, 'location': 3})
        mapstats = v_session.query(MapStat).filter(
            MapStat.key == MAPSTAT_TYPE['location']).all()
        mapstats = [(m.lat, m.lon, m.value) for m in mapstats]
        self.assertEqual(mapstats, [(378719, -1222732, 3)])

    def test_corrupt_lines(self):
        func, tmpfile = self._make_one()
        os.write(tmpfile[0], LINE + '\n')
        os.write(tmpfile[0], '3\t\\N\n')
        os.write(tmpfile[0], '4\t\\N\tabc\n')
        os.write(tmpfile[0], '5\t\\N\t1.0\t2.1\tabc\n')
        counter = func(self.archival_db_session, self.volatile_db_session, tmpfile[1])
        self.assertEqual(counter, 1)


class TestMain(CeleryTestCase):

    def _make_one(self):
        from ichnaea.importer import main
        data = mkstemp()
        return data, main

    def test_main(self):
        data, func = self._make_one()
        counter = func(['main', data[1]],
                       _archival_db=self.archival_db,
                       _volatile_db=self.volatile_db)
        self.assertEqual(counter, 0)

    def test_main_userid(self):
        data, func = self._make_one()
        counter = func(['main', data[1], '--userid=1'],
                       _archival_db=self.archival_db,
                       _volatile_db=self.volatile_db)
        self.assertEqual(counter, 0)
