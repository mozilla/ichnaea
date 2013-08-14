from datetime import datetime
from datetime import timedelta
from uuid import uuid4

from pyramid.testing import DummyRequest
from pyramid.testing import setUp
from pyramid.testing import tearDown
from unittest2 import TestCase

from ichnaea.db import Measure
from ichnaea.tests.base import AppTestCase


class TestContentViews(TestCase):

    def setUp(self):
        request = DummyRequest()
        self.config = setUp(request=request)

    def tearDown(self):
        tearDown()

    def _make_view(self, request):
        from ichnaea.content.views import ContentViews
        return ContentViews(request)

    def test_homepage(self):
        request = DummyRequest()
        inst = self._make_view(request)
        result = inst.homepage_view()
        self.assertEqual(result['page_title'], 'Overview')

    def test_map(self):
        request = DummyRequest()
        inst = self._make_view(request)
        result = inst.map_view()
        self.assertEqual(result['page_title'], 'Coverage Map')


class TestFunctionalContent(AppTestCase):

    def test_favicon(self):
        self.app.get('/favicon.ico', status=200)

    def test_homepage(self):
        result = self.app.get('/', status=200)
        self.assertTrue('Strict-Transport-Security' in result.headers)

    def test_not_found(self):
        self.app.get('/nobody-is-home', status=404)

    def test_map(self):
        self.app.get('/map', status=200)

    def test_map_csv(self):
        app = self.app
        session = self.db_slave_session
        wifi = '[{"key": "a"}]'
        measures = [Measure(lat=30000000, lon=40000000, wifi=wifi)]
        for i in range(101):
            measures.append(Measure(lat=10000000, lon=20000000, wifi=wifi))
        for i in range(11):
            measures.append(Measure(lat=20000000, lon=30000000, wifi=wifi))
        session.add_all(measures)
        session.commit()
        result = app.get('/map.csv', status=200)
        self.assertEqual(result.content_type, 'text/plain')
        text = result.text.replace('\r', '').strip('\n')
        text = text.split('\n')
        self.assertEqual(text, ['lat,lon,value', '1.0,2.0,3', '2.0,3.0,2'])

    def test_robots_txt(self):
        self.app.get('/robots.txt', status=200)

    def test_stats_json(self):
        app = self.app
        today = datetime.utcnow().date()
        yesterday = (today - timedelta(1)).strftime('%Y-%m-%d')
        two_days = (today - timedelta(2)).strftime('%Y-%m-%d')
        long_ago = (today - timedelta(40)).strftime('%Y-%m-%d')
        today = today.strftime('%Y-%m-%d')
        session = self.db_slave_session
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
        result = app.get('/stats.json', status=200)
        self.assertEqual(
            result.json, {'histogram': [
                {'num': 4, 'day': two_days},
                {'num': 5, 'day': yesterday},
                {'num': 7, 'day': today},
            ]}
        )


class TestStats(AppTestCase):

    def setUp(self):
        AppTestCase.setUp(self)
        request = DummyRequest()
        self.config = setUp(request=request)

    def tearDown(self):
        tearDown()
        AppTestCase.tearDown(self)

    def _make_view(self, request):
        from ichnaea.content.views import ContentViews
        return ContentViews(request)

    def test_stats_empty(self):
        request = DummyRequest()
        request.db_slave_session = self.db_slave_session
        inst = self._make_view(request)
        result = inst.stats_view()
        self.assertEqual(result['page_title'], 'Statistics')
        self.assertTrue('metrics' in result)
        self.assertEqual(result['leaders'], [])

    def test_stats(self):
        app = self.app
        app.get('/stats', status=200)
        uid = uuid4().hex
        nickname = 'World Tr\xc3\xa4veler'
        cell1 = {"mcc": 123, "mnc": 1, "lac": 2, "cid": 1234}
        cell2 = {"mcc": 123, "mnc": 1, "lac": 3, "cid": 456}
        cell3 = {"mcc": 123, "mnc": 1, "lac": 4, "cid": 456}
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0, "lon": 2.0,
                 "wifi": [{"key": "a"}], "cell": [cell1, cell2]},
                {"lat": 2.0, "lon": 3.0,
                 "wifi": [{"key": "b"}], "cell": [cell2, cell3]},
                {"lat": 2.0, "lon": 3.0,
                 "wifi": [{"key": "b"}], "cell": [cell3, cell3]},
            ]},
            headers={'X-Token': uid, 'X-Nickname': nickname},
            status=204)
        request = DummyRequest()
        request.db_slave_session = self.db_master_session
        inst = self._make_view(request)
        result = inst.stats_view()
        self.assertEqual(result['page_title'], 'Statistics')
        self.assertEqual(result['leaders'],
                         [{'nickname': nickname.decode('utf-8'),
                           'num': 3, 'token': uid[:8]}])
        self.assertEqual(
            result['metrics'],
            [{'name': 'Locations', 'value': 3},
             {'name': 'Cells', 'value': 6},
             {'name': 'Unique Cells', 'value': 3},
             {'name': 'Wifi APs', 'value': 3},
             {'name': 'Unique Wifi APs', 'value': 2}])


class TestLayout(TestCase):

    def setUp(self):
        request = DummyRequest()
        self.config = setUp(request=request)

    def tearDown(self):
        tearDown()

    def _make_layout(self):
        from ichnaea.content.views import Layout
        return Layout()

    def test_base_template(self):
        from chameleon.zpt.template import Macro
        layout = self._make_layout()
        self.assertEqual(layout.base_template.__class__, Macro)

    def test_base_macros(self):
        from chameleon.zpt.template import Macros
        layout = self._make_layout()
        self.assertEqual(layout.base_macros.__class__, Macros)
