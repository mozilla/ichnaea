from datetime import datetime
from datetime import timedelta
from uuid import uuid4

from ichnaea.db import Measure
from ichnaea.db import Score
from ichnaea.db import User
from ichnaea.tests.base import DBTestCase


class TestStats(DBTestCase):

    def test_histogram(self):
        from ichnaea.content.stats import histogram
        session = self.db_master_session
        today = datetime.utcnow().date()
        yesterday = (today - timedelta(1)).strftime('%Y-%m-%d')
        two_days = (today - timedelta(2)).strftime('%Y-%m-%d')
        long_ago = (today - timedelta(40)).strftime('%Y-%m-%d')
        today = today.strftime('%Y-%m-%d')
        wifi = '[{"key": "a"}]'
        measures = [
            Measure(lat=10000000, lon=20000000, time=today, wifi=wifi),
            Measure(lat=10000000, lon=20000000, time=today, wifi=wifi),
            Measure(lat=10000000, lon=20000000, time=yesterday, wifi=wifi),
            Measure(lat=10000000, lon=20000000, time=two_days, wifi=wifi),
            Measure(lat=10000000, lon=20000000, time=two_days, wifi=wifi),
            Measure(lat=10000000, lon=20000000, time=two_days, wifi=wifi),
            Measure(lat=10000000, lon=20000000, time=long_ago, wifi=wifi),
        ]
        session.add_all(measures)
        session.commit()
        result = histogram(session)
        self.assertEqual(result, [
            {'num': 4, 'day': two_days},
            {'num': 5, 'day': yesterday},
            {'num': 7, 'day': today},
        ])

    def test_map_csv(self):
        from ichnaea.content.stats import map_csv
        session = self.db_master_session
        wifi = '[{"key": "a"}]'
        measures = [Measure(lat=30000000, lon=40000000, wifi=wifi)]
        for i in range(101):
            measures.append(Measure(lat=10000000, lon=20000000, wifi=wifi))
        for i in range(11):
            measures.append(Measure(lat=20000000, lon=30000000, wifi=wifi))
        session.add_all(measures)
        session.commit()
        result = map_csv(session)
        text = result.replace('\r', '').strip('\n')
        text = text.split('\n')
        self.assertEqual(text, ['lat,lon,value', '1.0,2.0,3', '2.0,3.0,2'])

    def test_leaders(self):
        from ichnaea.content.stats import leaders
        session = self.db_master_session
        test_data = []
        for i in range(20):
            test_data.append((uuid4().hex, 7))
        highest = uuid4().hex
        test_data.append((highest, 10))
        lowest = uuid4().hex
        test_data.append((lowest, 5))
        for uid, value in test_data:
            user = User(token=uid, nickname=u'nick')
            session.add(user)
            session.flush()
            score = Score(userid=user.id, value=value)
            session.add(score)
        session.commit()
        # check the result
        result = leaders(session)
        self.assertEqual(len(result), 10)
        self.assertEqual(result[0]['token'], highest[:8])
        self.assertEqual(result[0]['num'], 10)
        self.assertTrue(lowest not in [r['token'] for r in result])
