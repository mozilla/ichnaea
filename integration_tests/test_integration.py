import argparse
import json
import requests
import time
from nose.tools import eq_
import os
from ichnaea.models import ApiKey, Cell, Wifi
from ichnaea.db import Database
from ichnaea.models import from_degrees, GEOIP_CITY_ACCURACY
from ichnaea.tests.base import (
    TestCase,
    FRANCE_MCC,
    FREMONT_IP,
    FREMONT_LAT,
    FREMONT_LON,
    PARIS_IP,
    PARIS_LAT,
    PARIS_LON,
)


HOST = 'localhost'


def do_submit(expected_status=204):
    wifi_data = [{"key": "0012AB12AB12"}, {"key": "00:34:cd:34:cd:34"}]
    payload = json.dumps({"items": [{"lat": 12.3456781,
                                     "lon": 23.4567892,
                                     "accuracy": 17,
                                     "wifi": wifi_data}]})

    while True:
        try:
            r = requests.post('http://127.0.0.1:7001/v1/submit',
                              data=payload)
            print r.status_code, time.time()
            assert r.status_code == expected_status
        except:
            pass


def do_search(apikey='test', use_ip=None):
    key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)

    payload = json.dumps({"radio": "gsm",
                          "cell": [dict(radio='umts', cid=4, **key)],
                          "wifi": [{"key": "A1"},
                                   {"key": "B2"},
                                   {"key": "C3"},
                                   {"key": "D4"}],
                          })

    if use_ip is None:
        headers = {'X_FORWARDED_FOR': PARIS_IP}
    else:
        headers = {'X_FORWARDED_FOR': use_ip}

    r = requests.post('http://127.0.0.1:7001/v1/search?key=%s' % apikey,
                      data=payload, headers=headers)

    return r.status_code, r.content


def main():
    parser = argparse.ArgumentParser(description='Test the ichnaea server')
    parser.add_argument('--search',
                        action='store_true',
                        help='Run a search test')
    parser.add_argument('--submit',
                        action='store_true',
                        help='Run a submit test')

    args = parser.parse_args()
    if args.search:
        do_search()
    elif args.submit:
        do_submit()
    else:
        parser.print_help()


class VaurienController(object):
    def __init__(self):
        self.headers = {'Content-type': 'application/json',
                        'Accept': 'text/plain'}

    def dummy(self, timeout=3):
        while True:
            resp = requests.put(self.url,
                                data=json.dumps({"name": "dummy"}),
                                headers=self.headers,
                                timeout=timeout)
            if json.loads(resp.content)['status'] == 'ok':
                break

        resp = requests.get(self.url)
        assert json.loads(resp.content)['behavior'] == 'dummy'

    def delay(self, delay_second=1, timeout=3):
        while True:
            resp = requests.put(self.url,
                                data=json.dumps({"name": "delay",
                                                 'sleep': delay_second}),
                                headers=self.headers,
                                timeout=timeout)
            if json.loads(resp.content)['status'] == 'ok':
                break

        resp = requests.get(self.url)
        assert json.loads(resp.content)['behavior'] == 'delay'

    def blackout(self):
        while True:
            resp = requests.put(self.url,
                                data=json.dumps({"name": "blackout"}),
                                headers=self.headers)

            if json.loads(resp.content)['status'] == 'ok':
                break

        resp = requests.get(self.url)
        assert json.loads(resp.content)['behavior'] == 'blackout'


class VaurienMySQL(VaurienController):
    def __init__(self):
        VaurienController.__init__(self)
        self.url = 'http://localhost:8080/behavior'


class VaurienRedis(VaurienController):
    def __init__(self):
        VaurienController.__init__(self)
        self.url = 'http://localhost:8090/behavior'


"""
results for (mysql behavior, redis_behavior)

Search isn't impacted by redis failures, so we should expect to see a
delay if mysql is slowed down and a timeout if mysql is blacked out.
"""
search_results = {}
search_results[('dummy', 'dummy')] = 200
search_results[('dummy', 'delay')] = 200
search_results[('dummy', 'blackout')] = 200

search_results[('delay', 'dummy')] = 200
search_results[('delay', 'delay')] = 200
search_results[('delay', 'blackout')] = 200

search_results[('blackout', 'dummy')] = 200
search_results[('blackout', 'delay')] = 200
search_results[('blackout', 'blackout')] = 200


class TestSearch(TestCase):
    """
    Search tests should only be affected by mysql outages.

    All redis tests are in one test case
    """

    def setUp(self):
        TestCase.setUp(self)

        self.redis = VaurienRedis()
        self.mysql = VaurienMySQL()

        uri = os.environ.get('SQLURI',
                             'mysql+pymysql://root:mysql@localhost/location')
        self.db = Database(uri)

        self.install_apikey()
        self.install_fixtures()

    def install_fixtures(self):
        session = self.db.session()
        PARIS_LAT_DEG = from_degrees(PARIS_LAT)
        PARIS_LON_DEG = from_degrees(PARIS_LON)
        qry = session.query(Cell)
        if qry.count() > 0:
            session.query(Cell).delete()

        lat = from_degrees(PARIS_LAT)
        lon = from_degrees(PARIS_LON)

        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        data = [
            Cell(lat=lat, lon=lon, radio=2, cid=4, **key),
            Cell(lat=lat + 20000, lon=lon + 40000, radio=2, cid=5, **key),
        ]
        session.add_all(data)

        if session.query(Wifi).count() > 0:
            session.query(Wifi).delete()

        wifis = [
            Wifi(key="A1", lat=PARIS_LAT_DEG, lon=PARIS_LON_DEG),
            Wifi(key="B2", lat=PARIS_LAT_DEG, lon=PARIS_LON_DEG),
            Wifi(key="C3", lat=PARIS_LAT_DEG, lon=PARIS_LON_DEG),
            Wifi(key="D4", lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.commit()

    def install_apikey(self):
        session = self.db.session()
        if session.query(ApiKey).filter(
           ApiKey.valid_key == 'test').count() > 0:
            session.query(ApiKey).delete()

        session.add(ApiKey(valid_key='test', maxreq=0))
        session.commit()

    def test_mysql_dummy(self):
        # this should pass, otherwise, vaurien has screwed up
        self.mysql.dummy()
        self.redis.dummy()
        status_code, content = do_search(use_ip=PARIS_IP)
        eq_(status_code, 200)
        expected = {u'status': u'ok',
                    u'lat': PARIS_LAT,
                    u'lon': PARIS_LON,
                    u'accuracy': 100}
        actual = json.loads(content)

        self.assertAlmostEquals(actual['status'], expected['status'])
        self.assertAlmostEquals(actual['lat'], expected['lat'])
        self.assertAlmostEquals(actual['lon'], expected['lon'])
        self.assertAlmostEquals(actual['accuracy'], expected['accuracy'])

    def test_mysql_delay(self):
        # this should pass, otherwise, vaurien has screwed up
        self.mysql.delay()
        self.redis.dummy()
        start = time.time()
        status_code, content = do_search()
        end = time.time()
        assert (end-start) > 1.0
        eq_(status_code, 200)
        eq_(json.loads(content), {"status": "ok",
                                  "lat": PARIS_LAT,
                                  "lon": PARIS_LON,
                                  "accuracy": 100})

    def test_mysql_blackout(self):
        # This test has been renamed so that it runs last
        self.mysql.blackout()
        self.redis.dummy()

        # MySQL blackouts will cause API key checking to be disabled
        status_code, content = do_search(apikey='invalid_key',
                                         use_ip=FREMONT_IP)

        # MySQL blackouts will force only geo-ip to work
        eq_(status_code, 200)
        actual = json.loads(content)
        expected = {"status": "ok",
                    "lat": FREMONT_LAT,
                    "lon": FREMONT_LON,
                    "accuracy": GEOIP_CITY_ACCURACY}

        # TODO: not sure why we need almost equal for geoip
        self.assertAlmostEquals(actual['status'], expected['status'])
        self.assertAlmostEquals(actual['lat'], expected['lat'])
        self.assertAlmostEquals(actual['lon'], expected['lon'])
        self.assertAlmostEquals(actual['accuracy'], expected['accuracy'])

    def test_redis_dummy(self):
        self.mysql.dummy()
        self.redis.dummy()
        status_code, content = do_search()
        eq_(status_code, 200)
        eq_(json.loads(content), {"status": "ok",
                                  "lat": PARIS_LAT,
                                  "lon": PARIS_LON,
                                  "accuracy": 100})

    def test_redis_delay(self):
        self.mysql.dummy()
        self.redis.delay()
        start = time.time()
        status_code, content = do_search()
        delta = time.time() - start
        # The delay in redis should not affect search
        self.assertTrue(delta < 1.0)
        eq_(status_code, 200)
        eq_(json.loads(content), {"status": "ok",
                                  "lat": PARIS_LAT,
                                  "lon": PARIS_LON,
                                  "accuracy": 100})

    def test_redis_blackout(self):
        self.mysql.dummy()
        self.redis.blackout()

        start = time.time()
        status_code, content = do_search()
        delta = time.time() - start
        # The redis blackout should not affect search at all
        self.assertTrue(delta < 1.0)
        eq_(status_code, 200)
        eq_(json.loads(content), {"status": "ok",
                                  "lat": PARIS_LAT,
                                  "lon": PARIS_LON,
                                  "accuracy": 100})
