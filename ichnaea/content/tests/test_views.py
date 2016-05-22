from calendar import timegm

import boto
from mock import MagicMock, patch
from pyramid.testing import DummyRequest
from pyramid import testing
import pytest

from ichnaea.content.views import (
    configure_content,
    ContentViews,
)
from ichnaea.models.content import (
    Stat,
    StatKey,
)
from ichnaea import util


class TestConfig(object):

    @pytest.yield_fixture(scope='function')
    def config(self):
        with testing.testConfig() as config:
            config.registry.skip_logging = set()
            yield config

    def test_assets(self, config):
        config.registry.settings['assets'] = {
            'url': 'http://127.0.0.1:9/foo'}
        assert configure_content(config)
        assert (config.registry.map_config['map_tiles_url'] ==
                'http://127.0.0.1:9/foo/tiles/{z}/{x}/{y}.png')

    def test_enabled(self, config):
        assert configure_content(config)

    def test_disabled(self, config):
        config.registry.settings['web'] = {'enabled': 'false'}
        assert not configure_content(config)


class TestContentViews(object):

    @pytest.yield_fixture(scope='function')
    def views(self, redis, ro_session):
        request = DummyRequest()
        with testing.testConfig(request=request) as config:
            config.include('pyramid_chameleon')
            setattr(request, 'db_ro_session', ro_session)
            setattr(request.registry, 'map_config', {})
            setattr(request.registry, 'redis_client', redis)
            yield ContentViews(request)

    def test_homepage(self, views):
        tiles_url = 'http://127.0.0.1:9/static/tiles/{z}/{x}/{y}.png'
        map_config = views.request.registry.map_config
        map_config['map_id_base'] = 'base.map'
        map_config['map_token'] = 'pk.123456'
        map_config['map_tiles_url'] = tiles_url
        result = views.homepage_view()

        assert result['page_title'] == 'Overview'
        assert (result['map_image_url'] ==
                tiles_url.format(z=0, x=0, y='0@2x'))
        assert (result['map_image_base_url'] ==
                ('http://a.tiles.mapbox.com/v4/base.map/'
                 '0/0/0@2x.png?access_token=pk.123456'))

    def test_map(self, views):
        tiles_url = 'http://127.0.0.1:7001/static/'
        map_config = views.request.registry.map_config
        map_config['map_id_base'] = 'base.map'
        map_config['map_id_labels'] = 'labels.map'
        map_config['map_tiles_url'] = tiles_url
        map_config['map_token'] = 'pk.123456'
        result = views.map_view()

        assert result['page_title'] == 'Map'
        assert result['map_id_base'] == 'base.map'
        assert result['map_id_labels'] == 'labels.map'
        assert result['map_tiles_url'] == tiles_url
        assert result['map_token'] == 'pk.123456'

    def test_stats(self, ro_session, ro_session_tracker, views):
        today = util.utcnow().date()
        stats = [
            Stat(key=StatKey.blue, time=today, value=2200000),
            Stat(key=StatKey.cell, time=today, value=2000000),
            Stat(key=StatKey.wifi, time=today, value=2000000),
            Stat(key=StatKey.unique_blue, time=today, value=1500000),
            Stat(key=StatKey.unique_cell, time=today, value=1000000),
            Stat(key=StatKey.unique_cell_ocid, time=today, value=1500000),
            Stat(key=StatKey.unique_wifi, time=today, value=2000000),
        ]
        ro_session.add_all(stats)
        ro_session.commit()
        ro_session_tracker(1)

        result = views.stats_view()
        ro_session_tracker(2)

        assert result['page_title'] == 'Statistics'
        assert (result['metrics1'] == [
            {'name': 'Bluetooth Networks', 'value': '1.50'},
            {'name': 'Bluetooth Observations', 'value': '2.20'},
            {'name': 'Wifi Networks', 'value': '2.00'},
            {'name': 'Wifi Observations', 'value': '2.00'},
        ])
        assert (result['metrics2'] == [
            {'name': 'MLS Cells', 'value': '1.00'},
            {'name': 'MLS Cell Observations', 'value': '2.00'},
            {'name': 'OpenCellID Cells', 'value': '1.50'},
        ])

        second_result = views.stats_view()
        assert second_result == result
        # no additional DB query was done
        ro_session_tracker(2)


class TestFunctionalContent(object):

    def test_content(self, app, ro_session_tracker, stats):
        app.get('/', status=200)
        app.get('/apple-touch-icon-precomposed.png', status=200)
        app.get('/api', status=200)
        app.get('/apps', status=200)
        app.get('/contact', status=200)
        app.get('/favicon.ico', status=200)
        app.get('/leaders', status=301)
        app.get('/leaders/weekly', status=301)
        app.get('/map', status=200)
        app.get('/nobody-is-home', status=404)
        app.get('/optout', status=200)
        app.get('/privacy', status=200)
        app.get('/robots.txt', status=200)
        app.get('/static/css/images/icons-000000@2x.png', status=200)
        ro_session_tracker(0)
        app.get('/stats/regions', status=200)
        ro_session_tracker(1)
        app.get('/stats', status=200)
        ro_session_tracker(9)
        stats.check(counter=[
            ('request', ['path:', 'method:get', 'status:200']),
            ('request', ['path:map', 'method:get', 'status:200']),
        ], timer=[
            ('request', ['path:', 'method:get']),
            ('request', ['path:map', 'method:get']),
        ])

    def test_downloads(self, app):
        mock_conn = MagicMock(name='conn')
        mock_bucket = MagicMock(name='bucket')
        mock_conn.return_value.lookup.return_value = mock_bucket
        key_prefix = 'export/MLS-'

        class MockKey(object):

            def __init__(self, name, size):
                self.name = key_prefix + name
                self.size = size

        mock_bucket.list.return_value = [
            MockKey('full-cell-export-2016-02-24T000000.csv.gz', 1024),
            MockKey('diff-cell-export-2016-02-26T110000.csv.gz', 1000),
            MockKey('diff-cell-export-2016-02-26T100000.csv.gz', 1000),
            MockKey('full-cell-export-2016-02-26T000000.csv.gz', 8192),
            MockKey('diff-cell-export-2016-02-26T120000.csv.gz', 1000),
        ]
        with patch.object(boto, 'connect_s3', mock_conn):
            result = app.get('/downloads', status=200)
            assert '0kB' not in result.text
            assert '1kB' in result.text
            assert '8kB' in result.text

        # calling the page again should use the cache
        with patch.object(boto, 'connect_s3', mock_conn):
            result = app.get('/downloads', status=200)
            assert '1kB' in result.text

        # The mock / S3 API was only called once
        assert len(mock_bucket.list.mock_calls) == 1

    def test_headers(self, app):
        result = app.get('/', status=200)
        assert 'Strict-Transport-Security' in result.headers
        assert 'X-Frame-Options' in result.headers

        assert 'Content-Security-Policy' in result.headers
        csp = result.headers['Content-Security-Policy']
        # make sure CSP_BASE interpolation worked
        assert "'self'" in csp
        # make sure map assets url interpolation worked
        assert '127.0.0.1:7001' in csp

    def test_map_json(self, app):
        result = app.get('/map.json', status=200)
        assert (result.json['tiles_url'] ==
                'http://127.0.0.1:7001/static/tiles/')

    def test_stats_blue_json(self, app, ro_session):
        today = util.utcnow().date()
        first_of_month = timegm(today.replace(day=1).timetuple()) * 1000
        ro_session.add(
            Stat(key=StatKey.unique_blue, time=today, value=2))
        ro_session.commit()
        result = app.get('/stats_blue.json', status=200)
        assert (result.json == {
            'series': [
                {'data': [[first_of_month, 2]],
                 'title': 'MLS Bluetooth'},
            ]}
        )
        second_result = app.get('/stats_blue.json', status=200)
        assert second_result.json == result.json

    def test_stats_cell_json(self, app, ro_session):
        today = util.utcnow().date()
        first_of_month = timegm(today.replace(day=1).timetuple()) * 1000
        ro_session.add(
            Stat(key=StatKey.unique_cell, time=today, value=2))
        ro_session.add(
            Stat(key=StatKey.unique_cell_ocid, time=today, value=5))
        ro_session.commit()
        result = app.get('/stats_cell.json', status=200)
        assert (result.json == {
            'series': [
                {'data': [[first_of_month, 2]],
                 'title': 'MLS Cells'},
                {'data': [[first_of_month, 5]],
                 'title': 'OCID Cells'},
            ]}
        )
        second_result = app.get('/stats_cell.json', status=200)
        assert second_result.json == result.json

    def test_stats_wifi_json(self, app, ro_session):
        today = util.utcnow().date()
        first_of_month = timegm(today.replace(day=1).timetuple()) * 1000
        ro_session.add(
            Stat(key=StatKey.unique_wifi, time=today, value=2))
        ro_session.commit()
        result = app.get('/stats_wifi.json', status=200)
        assert (result.json == {
            'series': [
                {'data': [[first_of_month, 2]],
                 'title': 'MLS WiFi'},
            ]}
        )
        second_result = app.get('/stats_wifi.json', status=200)
        assert second_result.json == result.json
