"""
Contains website related routes and views.
"""

from operator import itemgetter
import os

import boto
from boto.exception import S3ResponseError
from pyramid.decorator import reify
from pyramid.events import NewResponse
from pyramid.events import subscriber
from pyramid.httpexceptions import HTTPMovedPermanently
from pyramid.renderers import get_renderer
from pyramid.response import FileResponse
from pyramid.response import Response
from pyramid.view import view_config
import simplejson
from six.moves.urllib import parse as urlparse

from ichnaea.content.stats import (
    global_stats,
    histogram,
    leaders,
    regions,
)
from ichnaea.models.content import StatKey
from ichnaea import util

HERE = os.path.dirname(__file__)
IMAGE_PATH = os.path.join(HERE, 'static', 'images')
FAVICON_PATH = os.path.join(IMAGE_PATH, 'favicon.ico')
TOUCHICON_PATH = os.path.join(IMAGE_PATH, 'apple-touch-icon.png')
# cache year lookup, needs server restart after new year :)
THIS_YEAR = u'%s' % util.utcnow().year

CSP_BASE = "'self'"
CSP_POLICY = """\
default-src 'self' *.tiles.mapbox.com;
font-src {base};
img-src {base} {tiles} *.google-analytics.com *.tiles.mapbox.com data:;
script-src {base} *.google-analytics.com 'unsafe-eval';
style-src {base};
"""
CSP_POLICY = CSP_POLICY.replace("\n", ' ').strip()
LOCAL_TILES_BASE = 'http://127.0.0.1:7001/static/tiles/'
TILES_PATTERN = '{z}/{x}/{y}.png'
LOCAL_TILES = LOCAL_TILES_BASE + TILES_PATTERN
BASE_MAP_KEY = 'mozilla-webprod.map-05ad0a21'


def map_tiles_url(base_url):
    if base_url is None:
        return LOCAL_TILES
    elif not base_url.endswith('/'):  # pragma: no cover
        base_url = base_url + '/'
    return urlparse.urljoin(base_url, 'tiles/' + TILES_PATTERN)


def configure_content(config):
    config.add_view(favicon_view, name='favicon.ico',
                    http_cache=(86400, {'public': True}))
    config.registry.skip_logging.add('/favicon.ico')
    config.add_view(robotstxt_view, name='robots.txt',
                    http_cache=(86400, {'public': True}))
    config.registry.skip_logging.add('/robots.txt')
    config.add_view(touchicon_view, name='apple-touch-icon-precomposed.png',
                    http_cache=(86400, {'public': True}))
    config.registry.skip_logging.add('/apple-touch-icon-precomposed.png')
    config.add_static_view(
        name='static', path='ichnaea.content:static', cache_max_age=86400)

    # BBB: leaders_weekly is an alias for leaders
    config.add_route('leaders_weekly', '/leaders/weekly')
    config.add_route('leaders', '/leaders')
    config.add_route('stats_regions', '/stats/regions')
    config.add_route('stats', '/stats')

    config.scan('ichnaea.content.views')

    assets_url = config.registry.settings.get('assets', {}).get('url', None)
    config.registry.tiles_url = tiles_url = map_tiles_url(assets_url)
    result = urlparse.urlsplit(tiles_url)
    tiles = urlparse.urlunparse((result.scheme, result.netloc, '', '', '', ''))
    config.registry.csp = CSP_POLICY.format(base=CSP_BASE, tiles=tiles)


@subscriber(NewResponse)
def security_headers(event):
    response = event.response
    if response.content_type == 'text/html':
        csp = event.request.registry.csp
        response.headers.add('Strict-Transport-Security', 'max-age=31536000')
        response.headers.add('Content-Security-Policy', csp)
        response.headers.add('X-Content-Type-Options', 'nosniff')
        response.headers.add('X-XSS-Protection', '1; mode=block')
        response.headers.add('X-Frame-Options', 'DENY')


def s3_list_downloads(assets_bucket, assets_url, raven_client):
    files = {'full': [], 'diff1': [], 'diff2': []}

    if not assets_bucket:  # pragma: no cover
        return files

    if not assets_url.endswith('/'):  # pragma: no cover
        assets_url = assets_url + '/'

    conn = boto.connect_s3()
    bucket = conn.lookup(assets_bucket, validate=False)
    if bucket is None:  # pragma: no cover
        return files

    diff = []
    full = []
    try:
        for key in bucket.list(prefix='export/'):
            name = key.name.split('/')[-1]
            path = urlparse.urljoin(assets_url, key.name)
            # round to kilobyte
            size = int(round(key.size / 1024.0, 0))
            file = dict(name=name, path=path, size=size)
            if 'diff-' in name:
                diff.append(file)
            elif 'full-' in name:
                full.append(file)
    except S3ResponseError:  # pragma: no cover
        raven_client.captureException()
        return files

    half = len(diff) // 2 + len(diff) % 2
    diff = list(sorted(diff, key=itemgetter('name'), reverse=True))
    files['diff1'] = diff[:half]
    files['diff2'] = diff[half:]
    files['full'] = list(sorted(full, key=itemgetter('name'), reverse=True))
    return files


class ContentViews(object):

    def __init__(self, request):
        self.request = request
        self.session = request.db_ro_session
        self.redis_client = request.registry.redis_client

    @reify
    def base_template(self):
        renderer = get_renderer('templates/base.pt')
        return renderer.implementation().macros['layout']

    @property
    def this_year(self):
        return THIS_YEAR

    def _tiles_url(self):
        tiles_url = getattr(self.request.registry, 'tiles_url', None)
        if not tiles_url:
            tiles_url = map_tiles_url(None)
        return tiles_url

    def _get_cache(self, cache_key):
        cache_key = self.redis_client.cache_keys[cache_key]
        cached = self.redis_client.get(cache_key)
        if cached:
            return simplejson.loads(cached)
        return None

    def _set_cache(self, cache_key, data, ex=3600):
        cache_key = self.redis_client.cache_keys[cache_key]
        self.redis_client.set(cache_key, simplejson.dumps(data), ex=ex)

    @view_config(renderer='templates/homepage.pt', http_cache=3600)
    def homepage_view(self):
        map_url = self._tiles_url().format(z=0, x=0, y=0)
        scheme = urlparse.urlparse(self.request.url).scheme
        map_base_url = '%s://a.tiles.mapbox.com/v3/%s/0/0/0.png' % (
            scheme, BASE_MAP_KEY)
        return {
            'page_title': 'Overview',
            'map_url': map_url,
            'map_url_2': map_url.replace('/0.png', '/0@2x.png'),
            'map_base_url': map_base_url,
        }

    @view_config(renderer='templates/api.pt', name='api', http_cache=3600)
    def api_view(self):
        return {'page_title': 'API'}

    @view_config(renderer='templates/apps.pt', name='apps', http_cache=3600)
    def apps_view(self):
        return {'page_title': 'Client Applications'}

    @view_config(renderer='templates/contact.pt', name='contact',
                 http_cache=3600)
    def contact_view(self):
        return {'page_title': 'Contact Us'}

    @view_config(renderer='templates/downloads.pt', name='downloads',
                 http_cache=3600)
    def downloads_view(self):
        data = self._get_cache('downloads')
        if data is None:
            settings = self.request.registry.settings
            data = s3_list_downloads(
                settings['assets']['bucket'],
                settings['assets']['url'],
                self.request.registry.raven_client)
            self._set_cache('downloads', data, ex=1800)
        return {'page_title': 'Downloads', 'files': data}

    @view_config(renderer='templates/optout.pt', name='optout',
                 http_cache=3600)
    def optout_view(self):
        return {'page_title': 'Opt-Out'}

    @view_config(renderer='templates/privacy.pt', name='privacy',
                 http_cache=3600)
    def privacy_view(self):
        return {'page_title': 'Privacy Notice'}

    @view_config(renderer='templates/leaders.pt', route_name='leaders',
                 http_cache=3600)
    def leaders_view(self):
        data = self._get_cache('leaders')
        if data is None:
            data = [{
                'pos': lead[0] + 1,
                'num': lead[1]['num'],
                'nickname': lead[1]['nickname'],
                'anchor': lead[1]['nickname'],
            } for lead in enumerate(leaders(self.session))]
            self._set_cache('leaders', data)

        half = len(data) // 2 + len(data) % 2
        return {
            'page_title': 'Leaderboard',
            'leaders1': data[:half],
            'leaders2': data[half:],
        }

    @view_config(route_name='leaders_weekly')
    def leaders_weekly_view(self):
        return HTTPMovedPermanently(
            location=self.request.route_path('leaders'))

    @view_config(renderer='templates/map.pt', name='map', http_cache=3600)
    def map_view(self):
        return {'page_title': 'Map', 'tiles': self._tiles_url()}

    @view_config(
        renderer='json', name='map.json', http_cache=3600)
    def map_json(self):
        tiles_url = self._tiles_url()
        offset = tiles_url.find(TILES_PATTERN)
        base_url = tiles_url[:offset]
        return {'tiles_url': base_url}

    @view_config(renderer='json', name='stats_blue.json', http_cache=3600)
    def stats_blue_json(self):
        data = self._get_cache('stats_blue_json')
        if data is None:
            data = histogram(self.session, StatKey.unique_blue)
            self._set_cache('stats_blue_json', data)
        return {'series': [{'title': 'MLS Bluetooth', 'data': data[0]}]}

    @view_config(renderer='json', name='stats_cell.json', http_cache=3600)
    def stats_cell_json(self):
        data = self._get_cache('stats_cell_json')
        if data is None:
            mls_data = histogram(self.session, StatKey.unique_cell)
            ocid_data = histogram(self.session, StatKey.unique_cell_ocid)
            data = [
                {'title': 'MLS Cells', 'data': mls_data[0]},
                {'title': 'OCID Cells', 'data': ocid_data[0]},
            ]
            self._set_cache('stats_cell_json', data)
        return {'series': data}

    @view_config(renderer='json', name='stats_wifi.json', http_cache=3600)
    def stats_wifi_json(self):
        data = self._get_cache('stats_wifi_json')
        if data is None:
            data = histogram(self.session, StatKey.unique_wifi)
            self._set_cache('stats_wifi_json', data)
        return {'series': [{'title': 'MLS WiFi', 'data': data[0]}]}

    @view_config(renderer='templates/stats.pt', route_name='stats',
                 http_cache=3600)
    def stats_view(self):
        data = self._get_cache('stats')
        if data is None:
            data = {'leaders': [], 'metrics1': [], 'metrics2': []}
            metric_names = [
                ('1', StatKey.unique_blue.name, 'Bluetooth Networks'),
                ('1', StatKey.blue.name, 'Bluetooth Observations'),
                ('1', StatKey.unique_wifi.name, 'Wifi Networks'),
                ('1', StatKey.wifi.name, 'Wifi Observations'),
                ('2', StatKey.unique_cell.name, 'MLS Cells'),
                ('2', StatKey.cell.name, 'MLS Cell Observations'),
                ('2', StatKey.unique_cell_ocid.name, 'OpenCellID Cells'),
            ]
            metrics = global_stats(self.session)
            for i, mid, name in metric_names:
                data['metrics' + i].append(
                    {'name': name, 'value': metrics[mid]})
            self._set_cache('stats', data)

        result = {'page_title': 'Statistics'}
        result.update(data)
        return result

    @view_config(renderer='templates/stats_regions.pt',
                 route_name='stats_regions', http_cache=3600)
    def stats_regions_view(self):
        data = self._get_cache('stats_regions')
        if data is None:
            data = regions(self.session)
            self._set_cache('stats_regions', data)
        return {'page_title': 'Region Statistics', 'metrics': data}


def favicon_view(request):
    return FileResponse(FAVICON_PATH, request=request)


def touchicon_view(request):
    return FileResponse(TOUCHICON_PATH, request=request)


_robots_response = Response(content_type='text/plain', body='''\
User-agent: *
Disallow: /downloads
Disallow: /leaders
Disallow: /static/
Disallow: /v1/
Disallow: /v2/
Disallow: /__heartbeat__
Disallow: /__monitor__
Disallow: /__version__
''')


def robotstxt_view(context, request):
    return _robots_response
