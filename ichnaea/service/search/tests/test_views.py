from sqlalchemy import text
from webob.response import gzip_app_iter

from ichnaea.customjson import dumps, loads
from ichnaea.heka_logging import RAVEN_ERROR
from ichnaea.models import (
    Cell,
    Wifi,
    CELLID_LAC,
    CELL_MIN_ACCURACY,
    LAC_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
    GEOIP_CITY_ACCURACY,
    RADIO_TYPE,
)
from ichnaea.tests.base import (
    AppTestCase,
    FRANCE_MCC,
    FREMONT_IP,
    FREMONT_LAT,
    FREMONT_LON,
    BRAZIL_MCC,
    VIVO_MNC,
    SAO_PAULO_LAT,
    SAO_PAULO_LON,
    PORTO_ALEGRE_LAT,
    PORTO_ALEGRE_LON,
    PARIS_LAT,
    PARIS_LON,
)

from ichnaea.service.base import INVALID_API_KEY


class TestSearch(AppTestCase):

    def test_ok_cell(self):
        app = self.app
        session = self.db_slave_session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        lat = PARIS_LAT
        lon = PARIS_LON
        data = [
            Cell(lat=lat, lon=lon, radio=2, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=2, cid=5, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="umts", cid=4, **key),
                dict(radio="umts", cid=5, **key),
            ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": PARIS_LAT + 0.001,
                                    "lon": PARIS_LON + 0.002,
                                    "accuracy": CELL_MIN_ACCURACY})

        self.check_stats(
            total=9,
            timer=[('request.v1.search', 1),
                   ('search.accuracy.cell', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.cell_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.cell_found', 1),
                     ('search.no_cell_lac_found', 1),
                     ('search.no_geoip_found', 1),
                     ('search.country_from_mcc', 1)]
        )

    def test_ok_wifi(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="A1", lat=1.0, lon=1.0),
            Wifi(key="B2", lat=1.002, lon=1.004),
            Wifi(key="C3", lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json('/v1/search?key=test',
                            {"wifi": [
                                {"key": "A1"}, {"key": "B2"}, {"key": "C3"},
                            ]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": 1.001, "lon": 1.002,
                                    "accuracy": 248.6090897})

        self.check_stats(
            total=8,
            timer=[('request.v1.search', 1),
                   ('search.accuracy.wifi', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.wifi_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.wifi_found', 1),
                     ('search.no_geoip_found', 1),
                     ('search.no_country', 1)]
        )

    def test_not_found(self):
        app = self.app
        res = app.post_json('/v1/search?key=test',
                            {"cell": [{"mcc": FRANCE_MCC, "mnc": 2,
                                       "lac": 3, "cid": 4}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

        self.check_stats(counter=['search.api_key.test',
                                  'search.miss'])

    def test_wifi_not_found(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {"wifi": [
                            {"key": "abcd"}, {"key": "cdef"}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

        self.check_stats(counter=['search.api_key.test',
                                  'search.miss'])

    def test_wifi_not_found_cell_fallback(self):
        app = self.app
        session = self.db_slave_session
        lat = PARIS_LAT
        lon = PARIS_LON
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        data = [
            Wifi(key="abcd", lat=3, lon=3),
            Cell(lat=lat, lon=lon, radio=2, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=2, cid=5, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="umts", cid=4, **key),
                dict(radio="umts", cid=5, **key),
            ], "wifi": [
                {"key": "abcd"},
                {"key": "cdef"},
            ]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": PARIS_LAT + 0.001,
                                    "lon": PARIS_LON + 0.002,
                                    "accuracy": CELL_MIN_ACCURACY})

    def test_cell_miss_lac_hit(self):
        app = self.app
        session = self.db_slave_session
        lat = PARIS_LAT
        lon = PARIS_LON
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        data = [
            Cell(lat=lat, lon=lon, radio=2, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=2, cid=5, **key),
            Cell(lat=lat + 0.006, lon=lon + 0.006, radio=2, cid=6, **key),
            Cell(lat=lat + 0.0026666, lon=lon + 0.0033333,
                 radio=2, cid=CELLID_LAC,
                 range=500000, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="umts", cid=7, **key),
            ]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": PARIS_LAT + 0.0026666,
                                    "lon": PARIS_LON + 0.0033333,
                                    "accuracy": 500000})

    def test_cell_hit_ignores_lac(self):
        app = self.app
        session = self.db_slave_session
        lat = PARIS_LAT
        lon = PARIS_LON
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        data = [
            Cell(lat=lat, lon=lon, radio=2, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=2, cid=5, **key),
            Cell(lat=lat + 0.006, lon=lon + 0.006, radio=2, cid=6, **key),
            Cell(lat=lat + 0.0026666,
                 lon=lon + 0.0033333, radio=2, cid=CELLID_LAC,
                 range=50000, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="umts", cid=5, **key),
            ]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": PARIS_LAT + 0.002,
                                    "lon": PARIS_LON + 0.004,
                                    "accuracy": CELL_MIN_ACCURACY})

    def test_lac_miss(self):
        app = self.app
        session = self.db_slave_session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        lat = PARIS_LAT
        lon = PARIS_LON
        data = [
            Cell(lat=lat, lon=lon, radio=2, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=2, cid=5, **key),
            Cell(lat=1.006, lon=1.006, radio=2, cid=6, **key),
            Cell(lat=1.0026666, lon=1.0033333, radio=2, cid=CELLID_LAC,
                 range=50000, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="umts", mcc=FRANCE_MCC, mnc=2, lac=4, cid=5),
            ]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

    def test_cell_ignore_invalid_lac_cid(self):
        app = self.app
        session = self.db_slave_session
        lat = PARIS_LAT
        lon = PARIS_LON

        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        ignored_key = dict(mcc=FRANCE_MCC, mnc=2, lac=-1, cid=-1)

        data = [
            Cell(lat=lat, lon=lon, radio=2, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=2, cid=5, **key),
            Cell(lat=lat, lon=lon, radio=2, **ignored_key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=3, **ignored_key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="umts", cid=4, **key),
                dict(radio="umts", cid=5, **key),

                dict(radio="umts", cid=5, mcc=FRANCE_MCC, mnc=2, lac=-1),
                dict(radio="umts", cid=-1, mcc=FRANCE_MCC, mnc=2, lac=3),
            ]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": PARIS_LAT + 0.001,
                                    "lon": PARIS_LON + 0.002,
                                    "accuracy": CELL_MIN_ACCURACY})

    def test_geoip_fallback(self):
        app = self.app
        res = app.post_json(
            '/v1/search?key=test',
            {"wifi": [
                {"key": "Porky"}, {"key": "Piggy"},
                {"key": "Davis"}, {"key": "McSnappy"},
            ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': FREMONT_IP},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": FREMONT_LAT,
                                    "lon": FREMONT_LON,
                                    "accuracy": GEOIP_CITY_ACCURACY})

        self.check_stats(
            total=8,
            timer=[('request.v1.search', 1),
                   ('search.accuracy.geoip', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.geoip_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.no_wifi_found', 1),
                     ('search.geoip_city_found', 1),
                     ('search.country_from_geoip', 1)]
        )

    def test_empty_request_means_geoip(self):
        app = self.app
        res = app.post_json(
            '/v1/search?key=test', {},
            extra_environ={'HTTP_X_FORWARDED_FOR': FREMONT_IP},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": FREMONT_LAT,
                                    "lon": FREMONT_LON,
                                    "accuracy": GEOIP_CITY_ACCURACY})

        self.check_stats(
            total=7,
            timer=[('request.v1.search', 1),
                   ('search.accuracy.geoip', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.geoip_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.geoip_city_found', 1),
                     ('search.country_from_geoip', 1)]
        )

    def test_cell_disagrees_with_country(self):
        # This test checks that when a cell is at a lat/lon that
        # is not in the country determined by mcc (say) we reject
        # the query. Really we should start filtering these out
        # on ingress as well, but this is a double-check.

        app = self.app
        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        data = [
            Cell(lat=PARIS_LAT,
                 lon=PARIS_LON,
                 radio=0, cid=6789, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="gsm", cid=6789, **key),
            ]},
            status=200)

        self.check_stats(
            total=9,
            timer=[
                ('request.v1.search', 1),
            ],
            counter=[
                ('search.api_key.test', 1),
                ('request.v1.search.200', 1),
                ('search.anomaly.cell_country_mismatch', 1),
                ('search.country_from_mcc', 1),
                ('search.no_geoip_found', 1),
                ('search.cell_found', 1),
                ('search.no_cell_lac_found', 1),
                ('search.miss', 1),
            ]
        )
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

    def test_lac_disagrees_with_country(self):
        # This test checks that when a LAC is at a lat/lon that
        # is not in the country determined by mcc (say) we reject
        # the query. Really we should start filtering these out
        # on ingress as well, but this is a double-check.

        app = self.app
        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        data = [
            Cell(lat=PARIS_LAT,
                 lon=PARIS_LON,
                 radio=0, cid=CELLID_LAC, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="gsm", cid=6789, **key),
            ]},
            status=200)

        self.check_stats(
            total=9,
            timer=[
                ('request.v1.search', 1),
            ],
            counter=[
                ('search.api_key.test', 1),
                ('request.v1.search.200', 1),
                ('search.anomaly.cell_lac_country_mismatch', 1),
                ('search.country_from_mcc', 1),
                ('search.no_geoip_found', 1),
                ('search.no_cell_found', 1),
                ('search.cell_lac_found', 1),
                ('search.miss', 1),
            ]
        )
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

    def test_wifi_disagrees_with_country(self):
        # This test checks that when a wifi is at a lat/lon that
        # is not in the country determined by geoip, we drop back
        # to the geoip, rejecting the wifi.

        app = self.app
        session = self.db_slave_session

        # This lat/lon is Paris, France
        (lat, lon) = (PARIS_LAT, PARIS_LON)

        wifi1 = dict(key="1234567890ab")
        wifi2 = dict(key="1234890ab567")
        wifi3 = dict(key="4321890ab567")
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"wifi": [wifi1, wifi2, wifi3]},
            extra_environ={'HTTP_X_FORWARDED_FOR': FREMONT_IP},
            status=200)

        self.check_stats(
            total=9,
            timer=[
                ('request.v1.search', 1),
                ('search.accuracy.geoip', 1),
            ],
            counter=[
                ('search.api_key.test', 1),
                ('request.v1.search.200', 1),
                ('search.anomaly.wifi_country_mismatch', 1),
                ('search.country_from_geoip', 1),
                ('search.geoip_city_found', 1),
                ('search.wifi_found', 1),
                ('search.geoip_hit', 1),
            ]
        )
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": FREMONT_LAT,
                                    "lon": FREMONT_LON,
                                    "accuracy": GEOIP_CITY_ACCURACY})

    def test_cell_disagrees_with_lac(self):
        # This test checks that when a cell is at a lat/lon that
        # is not in the LAC associated with it, we drop back
        # to the LAC. This likely represents some kind of internal
        # database consistency error, but it might also just be a
        # new cell that hasn't been integrated yet or something.

        app = self.app
        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        data = [
            Cell(lat=PORTO_ALEGRE_LAT,
                 lon=PORTO_ALEGRE_LON,
                 radio=0, cid=6789, **key),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=0, cid=CELLID_LAC, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="gsm", cid=6789, **key),
            ]},
            status=200)

        self.check_stats(
            total=10,
            timer=[
                ('request.v1.search', 1),
                ('search.accuracy.cell_lac', 1)
            ],
            counter=[
                ('search.api_key.test', 1),
                ('request.v1.search.200', 1),
                ('search.anomaly.cell_cell_lac_mismatch', 1),
                ('search.country_from_mcc', 1),
                ('search.no_geoip_found', 1),
                ('search.cell_lac_found', 1),
                ('search.cell_found', 1),
                ('search.cell_lac_hit', 1),
            ]
        )
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": SAO_PAULO_LAT,
                                    "lon": SAO_PAULO_LON,
                                    "accuracy": LAC_MIN_ACCURACY})

    def test_wifi_disagrees_with_lac(self):
        # This test checks that when a wifi is at a lat/lon that
        # is not in the LAC associated with our query, we drop back
        # to the LAC.

        app = self.app
        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key="1234567890ab")
        wifi2 = dict(key="1234890ab567")
        wifi3 = dict(key="4321890ab567")
        lat = PORTO_ALEGRE_LAT
        lon = PORTO_ALEGRE_LON
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=0, cid=CELLID_LAC, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm",
             "cell": [
                 dict(radio="gsm", cid=6789, **key),
             ],
             "wifi": [wifi1, wifi2, wifi3]},
            status=200)

        self.check_stats(
            total=11,
            timer=[
                ('request.v1.search', 1),
                ('search.accuracy.cell_lac', 1)
            ],
            counter=[
                ('search.api_key.test', 1),
                ('request.v1.search.200', 1),
                ('search.anomaly.wifi_cell_lac_mismatch', 1),
                ('search.country_from_mcc', 1),
                ('search.no_geoip_found', 1),
                ('search.cell_lac_found', 1),
                ('search.wifi_found', 1),
                ('search.cell_lac_hit', 1),
            ]
        )
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": SAO_PAULO_LAT,
                                    "lon": SAO_PAULO_LON,
                                    "accuracy": LAC_MIN_ACCURACY})

    def test_wifi_disagrees_with_cell(self):
        # This test checks that when a wifi is at a lat/lon that
        # is not in the cell associated with our query, we drop back
        # to the cell.

        app = self.app
        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key="1234567890ab")
        wifi2 = dict(key="1234890ab567")
        wifi3 = dict(key="4321890ab567")
        lat = PORTO_ALEGRE_LAT
        lon = PORTO_ALEGRE_LON
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=0, cid=6789, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm",
             "cell": [
                 dict(radio="gsm", cid=6789, **key),
             ],
             "wifi": [wifi1, wifi2, wifi3]},
            status=200)

        self.check_stats(
            total=11,
            timer=[
                ('request.v1.search', 1),
                ('search.accuracy.cell', 1)
            ],
            counter=[
                ('search.api_key.test', 1),
                ('request.v1.search.200', 1),
                ('search.anomaly.wifi_cell_mismatch', 1),
                ('search.country_from_mcc', 1),
                ('search.no_geoip_found', 1),
                ('search.no_cell_lac_found', 1),
                ('search.cell_found', 1),
                ('search.wifi_found', 1),
                ('search.cell_hit', 1),
            ]
        )
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": SAO_PAULO_LAT,
                                    "lon": SAO_PAULO_LON,
                                    "accuracy": CELL_MIN_ACCURACY})

    def test_cell_agrees_with_lac(self):
        # This test checks that when a cell is at a lat/lon that
        # is inside its enclosing LAC, we accept it and tighten
        # our accuracy accordingly.

        app = self.app
        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        data = [
            Cell(lat=SAO_PAULO_LAT + 0.002,
                 lon=SAO_PAULO_LON + 0.002,
                 radio=0, cid=6789, **key),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=0, cid=CELLID_LAC, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="gsm", cid=6789, **key),
            ]},
            status=200)

        self.check_stats(
            total=9,
            timer=[
                ('request.v1.search', 1),
                ('search.accuracy.cell', 1)
            ],
            counter=[
                ('search.api_key.test', 1),
                ('request.v1.search.200', 1),
                ('search.country_from_mcc', 1),
                ('search.no_geoip_found', 1),
                ('search.cell_lac_found', 1),
                ('search.cell_found', 1),
                ('search.cell_hit', 1),
            ]
        )
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": SAO_PAULO_LAT + 0.002,
                                    "lon": SAO_PAULO_LON + 0.002,
                                    "accuracy": CELL_MIN_ACCURACY})

    def test_wifi_agrees_with_cell(self):
        # This test checks that when a wifi is at a lat/lon that
        # is inside its enclosing cell, we accept it and tighten
        # our accuracy accordingly.

        app = self.app
        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key="1234567890ab")
        wifi2 = dict(key="1234890ab567")
        wifi3 = dict(key="4321890ab567")
        lat = SAO_PAULO_LAT + 0.002
        lon = SAO_PAULO_LON + 0.002
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=0, cid=6789, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {
                "radio": "gsm",
                "cell": [
                    dict(radio="gsm", cid=6789, **key),
                ],
                "wifi": [wifi1, wifi2, wifi3]
            },
            status=200)

        self.check_stats(
            total=10,
            timer=[
                ('request.v1.search', 1),
                ('search.accuracy.wifi', 1)
            ],
            counter=[
                ('search.api_key.test', 1),
                ('request.v1.search.200', 1),
                ('search.country_from_mcc', 1),
                ('search.no_geoip_found', 1),
                ('search.no_cell_lac_found', 1),
                ('search.wifi_found', 1),
                ('search.cell_found', 1),
                ('search.wifi_hit', 1),
            ]
        )
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": SAO_PAULO_LAT + 0.002,
                                    "lon": SAO_PAULO_LON + 0.002,
                                    "accuracy": WIFI_MIN_ACCURACY})

    def test_wifi_agrees_with_lac(self):
        # This test checks that when a wifi is at a lat/lon that
        # is inside its enclosing LAC, we accept it and tighten
        # our accuracy accordingly.

        app = self.app
        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key="1234567890ab")
        wifi2 = dict(key="1234890ab567")
        wifi3 = dict(key="4321890ab567")
        lat = SAO_PAULO_LAT + 0.002
        lon = SAO_PAULO_LON + 0.002
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=0, cid=CELLID_LAC, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {
                "radio": "gsm",
                "cell": [
                    dict(radio="gsm", cid=6789, **key),
                ],
                "wifi": [wifi1, wifi2, wifi3]
            },
            status=200)

        self.check_stats(
            total=10,
            timer=[
                ('request.v1.search', 1),
                ('search.accuracy.wifi', 1)
            ],
            counter=[
                ('search.api_key.test', 1),
                ('request.v1.search.200', 1),
                ('search.country_from_mcc', 1),
                ('search.no_geoip_found', 1),
                ('search.no_cell_found', 1),
                ('search.wifi_found', 1),
                ('search.cell_lac_found', 1),
                ('search.wifi_hit', 1),
            ]
        )
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": SAO_PAULO_LAT + 0.002,
                                    "lon": SAO_PAULO_LON + 0.002,
                                    "accuracy": WIFI_MIN_ACCURACY})

    def test_wifi_agrees_with_cell_and_lac(self):
        # This test checks that when a wifi is at a lat/lon that
        # is inside its enclosing LAC and cell, we accept it and
        # tighten our accuracy accordingly.

        app = self.app
        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key="1234567890ab")
        wifi2 = dict(key="1234890ab567")
        wifi3 = dict(key="4321890ab567")
        lat = SAO_PAULO_LAT + 0.002
        lon = SAO_PAULO_LON + 0.002
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=0, cid=6789, **key),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=0, cid=CELLID_LAC, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {
                "radio": "gsm",
                "cell": [
                    dict(radio="gsm", cid=6789, **key),
                ],
                "wifi": [wifi1, wifi2, wifi3]
            },
            status=200)

        self.check_stats(
            total=10,
            timer=[
                ('request.v1.search', 1),
                ('search.accuracy.wifi', 1)
            ],
            counter=[
                ('search.api_key.test', 1),
                ('request.v1.search.200', 1),
                ('search.country_from_mcc', 1),
                ('search.no_geoip_found', 1),
                ('search.wifi_found', 1),
                ('search.cell_found', 1),
                ('search.cell_lac_found', 1),
                ('search.wifi_hit', 1),
            ]
        )
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": SAO_PAULO_LAT + 0.002,
                                    "lon": SAO_PAULO_LON + 0.002,
                                    "accuracy": WIFI_MIN_ACCURACY})

    def test_error(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {"cell": []}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)

    def test_error_unknown_key(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {"foo": 0}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)

    def test_error_no_mapping(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', [1], status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)

    def test_no_valid_keys(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {"wifi": [
                            {"key": ":"}, {"key": ".-"}]},
                            status=200)
        self.assertEqual(res.json, {"status": "not_found"})

    def test_no_json(self):
        app = self.app
        res = app.post('/v1/search?key=test', "\xae", status=400)
        self.assertTrue('errors' in res.json)
        self.check_stats(counter=['search.api_key.test'])

    def test_gzip(self):
        app = self.app
        data = {"cell": [{"mcc": FRANCE_MCC, "mnc": 2, "lac": 3, "cid": 4}]}
        body = ''.join(gzip_app_iter(dumps(data)))
        headers = {
            'Content-Encoding': 'gzip',
        }
        res = app.post('/v1/search?key=test', body, headers=headers,
                       content_type='application/json', status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

    def test_no_api_key(self):
        app = self.app
        session = self.db_slave_session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3, cid=4)
        session.add(Cell(
            lat=PARIS_LAT,
            lon=PARIS_LON,
            radio=RADIO_TYPE['umts'], **key)
        )
        session.commit()

        res = app.post_json(
            '/v1/search',
            {"radio": "gsm", "cell": [
                dict(radio="umts", **key),
            ]},
            status=400)
        self.assertEqual(res.json, loads(INVALID_API_KEY))
        self.check_stats(counter=['search.no_api_key'])

    def test_unknown_api_key(self):
        app = self.app
        session = self.db_slave_session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3, cid=4)
        session.add(Cell(
            lat=PARIS_LAT,
            lon=PARIS_LON,
            radio=RADIO_TYPE['umts'], **key)
        )
        session.commit()

        res = app.post_json(
            '/v1/search?key=unknown_key',
            {"radio": "gsm", "cell": [
                dict(radio="umts", **key),
            ]},
            status=400)
        self.assertEqual(res.json, loads(INVALID_API_KEY))
        self.check_stats(counter=['search.unknown_api_key'])


class TestSearchErrors(AppTestCase):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_master.engine)
        super(TestSearchErrors, self).tearDown()

    def test_database_error(self):
        app = self.app
        session = self.db_slave_session
        stmt = text("drop table wifi;")
        session.execute(stmt)

        res = app.post_json(
            '/v1/search?key=test',
            {"wifi": [
                {"key": "A1"}, {"key": "B2"},
                {"key": "C3"}, {"key": "D4"},
            ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': FREMONT_IP},
        )

        self.assertEqual(res.json, {"status": "ok",
                                    "lat": FREMONT_LAT,
                                    "lon": FREMONT_LON,
                                    "accuracy": GEOIP_CITY_ACCURACY})

        self.check_stats(
            timer=['request.v1.search'],
            counter=[
                'request.v1.search.200',
                'search.geoip_hit',
                'search.no_wifi_found',
                'search.wifi_error',
            ],
        )
        self.check_expected_heka_messages(
            sentry=[('msg', RAVEN_ERROR, 1)]
        )
