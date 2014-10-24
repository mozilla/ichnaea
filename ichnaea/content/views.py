import os
import urlparse

import boto
from boto.exception import S3ResponseError
from pyramid.decorator import reify
from pyramid.events import NewResponse
from pyramid.events import subscriber
from pyramid.renderers import get_renderer
from pyramid.response import FileResponse
from pyramid.response import Response
from pyramid.view import view_config

from ichnaea.content.stats import (
    countries,
    global_stats,
    histogram,
    leaders,
    leaders_weekly,
)
from ichnaea.customjson import dumps, loads
from ichnaea.logging import RAVEN_ERROR
from ichnaea import util

HERE = os.path.dirname(__file__)
IMAGE_PATH = os.path.join(HERE, 'static', 'images')
FAVICON_PATH = os.path.join(IMAGE_PATH, 'favicon.ico')
TOUCHICON_PATH = os.path.join(IMAGE_PATH, 'apple-touch-icon.png')
# cache year lookup, needs server restart after new year :)
THIS_YEAR = unicode(util.utcnow().year)

CSP_BASE = "'self' https://*.cdn.mozilla.net"
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

CACHE_KEYS = {
    'downloads': 'cache_download_files_2',
    'leaders': 'cache_leaders_2',
    'leaders_weekly': 'cache_leaders_weekly',
    'stats': 'cache_stats',
    'stats_countries': 'cache_stats_countries',
    'stats_cell_json': 'cache_stats_cell_json',
    'stats_wifi_json': 'cache_stats_wifi_json',
}


def map_tiles_url(base_url):
    if base_url is None:
        return LOCAL_TILES
    elif not base_url.endswith('/'):  # pragma: no cover
        base_url = base_url + '/'
    return urlparse.urljoin(base_url, 'tiles/' + TILES_PATTERN)


def configure_content(config):
    config.add_view(favicon_view, name='favicon.ico',
                    http_cache=(86400, {'public': True}))
    config.add_view(robotstxt_view, name='robots.txt',
                    http_cache=(86400, {'public': True}))
    config.add_view(touchicon_view, name='apple-touch-icon-precomposed.png',
                    http_cache=(86400, {'public': True}))
    config.add_static_view(
        name='static', path='ichnaea.content:static', cache_max_age=3600)

    config.add_route('leaders_weekly', '/leaders/weekly')
    config.add_route('leaders', '/leaders')

    config.add_route('stats_countries', '/stats/countries')
    config.add_route('stats', '/stats')

    config.scan('ichnaea.content.views')

    assets_url = config.registry.settings.get('assets_url', None)
    config.registry.tiles_url = tiles_url = map_tiles_url(assets_url)
    result = urlparse.urlsplit(tiles_url)
    tiles = urlparse.urlunparse((result.scheme, result.netloc, '', '', '', ''))
    config.registry.csp = CSP_POLICY.format(base=CSP_BASE, tiles=tiles)


@subscriber(NewResponse)
def security_headers(event):
    response = event.response
    if response.content_type == 'text/html':
        csp = event.request.registry.csp
        response.headers.add("Strict-Transport-Security", "max-age=31536000")
        response.headers.add("Content-Security-Policy", csp)
        response.headers.add("X-Content-Type-Options", "nosniff")
        response.headers.add("X-XSS-Protection", "1; mode=block")
        response.headers.add("X-Frame-Options", "DENY")


def s3_list_downloads(assets_bucket, assets_url, heka_client):
    if not assets_url.endswith('/'):  # pragma: no cover
        assets_url = assets_url + '/'

    conn = boto.connect_s3()
    bucket = conn.lookup(assets_bucket, validate=False)
    if bucket is None:  # pragma: no cover
        return []
    files = []
    try:
        for key in bucket.list(prefix='export/'):
            name = key.name.split('/')[-1]
            path = urlparse.urljoin(assets_url, key.name)
            # round to kilobyte
            size = int(round(key.size / 1024.0, 0))
            files.append(dict(name=name, path=path, size=size))
    except S3ResponseError:  # pragma: no cover
        heka_client.raven(RAVEN_ERROR)
        return []
    return sorted(files, reverse=True)


class Layout(object):

    @reify
    def base_template(self):
        renderer = get_renderer("templates/base.pt")
        return renderer.implementation().macros['layout']

    @reify
    def base_macros(self):
        renderer = get_renderer("templates/base_macros.pt")
        return renderer.implementation().macros

    @property
    def this_year(self):
        return THIS_YEAR


class ContentViews(Layout):

    def __init__(self, request):
        self.request = request

    def _tiles_url(self):
        tiles_url = getattr(self.request.registry, 'tiles_url', None)
        if not tiles_url:
            tiles_url = map_tiles_url(None)
        return tiles_url

    @view_config(renderer='templates/homepage.pt', http_cache=3600)
    def homepage_view(self):
        tiles_url = self._tiles_url()
        map_url = tiles_url.format(z=0, x=0, y=0)
        scheme = urlparse.urlparse(self.request.url).scheme
        map_base_url = '%s://a.tiles.mapbox.com/v3/%s/0/0/0.png' % (
            scheme, BASE_MAP_KEY)
        return {
            'page_title': 'Overview',
            'map_url': map_url,
            'map_url_2': map_url.replace('/0.png', '/0@2x.png'),
            'map_base_url': map_base_url,
        }

    @view_config(renderer='templates/api.pt',
                 name="api", http_cache=3600)
    def api_view(self):
        return {'page_title': 'API'}

    @view_config(renderer='templates/apps.pt',
                 name="apps", http_cache=3600)
    def apps_view(self):
        return {'page_title': 'Client Applications'}

    @view_config(renderer='templates/contact.pt',
                 name="contact", http_cache=3600)
    def contact_view(self):
        return {'page_title': 'Contact Us'}

    @view_config(renderer='templates/downloads.pt',
                 name="downloads", http_cache=3600)
    def downloads_view(self):
        redis_client = self.request.registry.redis_client
        cache_key = CACHE_KEYS['downloads']
        cached = redis_client.get(cache_key)
        if cached:
            data = loads(cached)
        else:
            settings = self.request.registry.settings
            assets_bucket = settings['s3_assets_bucket']
            assets_url = settings['assets_url']
            heka_client = self.request.registry.heka_client
            data = s3_list_downloads(assets_bucket, assets_url, heka_client)
            # cache the download files, expire after 10 minutes
            redis_client.set(cache_key, dumps(data), ex=600)
        return {'page_title': 'Downloads', 'files': data}

    @view_config(renderer='templates/optout.pt',
                 name="optout", http_cache=3600)
    def optout_view(self):
        return {'page_title': 'Opt-Out'}

    @view_config(renderer='templates/privacy.pt',
                 name="privacy", http_cache=3600)
    def privacy_view(self):
        return {'page_title': 'Privacy Notice'}

    @view_config(renderer='templates/leaders.pt',
                 route_name="leaders", http_cache=3600)
    def leaders_view(self):
        redis_client = self.request.registry.redis_client
        cache_key = CACHE_KEYS['leaders']
        cached = redis_client.get(cache_key)

        if cached:
            data = loads(cached)
        else:
            session = self.request.db_slave_session
            data = list(enumerate(leaders(session)))
            data = [
                {
                    'pos': l[0] + 1,
                    'num': l[1]['num'],
                    'nickname': l[1]['nickname'],
                    'anchor': l[1]['nickname'],
                } for l in data]
            redis_client.set(cache_key, dumps(data), ex=600)

        half = len(data) // 2 + len(data) % 2
        leaders1 = data[:half]
        leaders2 = data[half:]
        return {
            'page_title': 'Leaderboard',
            'leaders1': leaders1,
            'leaders2': leaders2,
        }

    @view_config(renderer='templates/leaders_weekly.pt',
                 route_name="leaders_weekly", http_cache=3600)
    def leaders_weekly_view(self):
        redis_client = self.request.registry.redis_client
        cache_key = CACHE_KEYS['leaders_weekly']
        cached = redis_client.get(cache_key)

        if cached:
            data = loads(cached)
        else:
            session = self.request.db_slave_session
            data = {
                'new_cell': {'leaders1': [], 'leaders2': []},
                'new_wifi': {'leaders1': [], 'leaders2': []},
            }
            for name, value in leaders_weekly(session).items():
                value = [
                    {
                        'pos': l[0] + 1,
                        'num': l[1]['num'],
                        'nickname': l[1]['nickname'],
                    } for l in list(enumerate(value))]
                half = len(value) // 2 + len(value) % 2
                data[name] = {
                    'leaders1': value[:half],
                    'leaders2': value[half:],
                }
            redis_client.set(cache_key, dumps(data), ex=3600)

        return {
            'page_title': 'Weekly Leaderboard',
            'scores': data,
        }

    @view_config(renderer='templates/map.pt', name="map", http_cache=3600)
    def map_view(self):
        return {'page_title': 'Map', 'tiles': self._tiles_url()}

    @view_config(
        renderer='json', name="map.json", http_cache=3600)
    def map_json(self):
        tiles_url = self._tiles_url()
        offset = tiles_url.find(TILES_PATTERN)
        base_url = tiles_url[:offset]
        return {'tiles_url': base_url}

    @view_config(
        renderer='json', name="stats_cell.json", http_cache=3600)
    def stats_cell_json(self):
        redis_client = self.request.registry.redis_client
        cache_key = CACHE_KEYS['stats_cell_json']
        cached = redis_client.get(cache_key)
        if cached:
            data = loads(cached)
        else:
            session = self.request.db_slave_session
            mls_data = histogram(session, 'unique_cell')
            ocid_data = histogram(session, 'unique_ocid_cell')
            data = [
                {'title': 'MLS Cells', 'data': mls_data[0]},
                {'title': 'OCID Cells', 'data': ocid_data[0]},
            ]
            redis_client.set(cache_key, dumps(data), ex=3600)
        return {'series': data}

    @view_config(
        renderer='json', name="stats_wifi.json", http_cache=3600)
    def stats_wifi_json(self):
        redis_client = self.request.registry.redis_client
        cache_key = CACHE_KEYS['stats_wifi_json']
        cached = redis_client.get(cache_key)
        if cached:
            data = loads(cached)
        else:
            session = self.request.db_slave_session
            data = histogram(session, 'unique_wifi')
            redis_client.set(cache_key, dumps(data), ex=3600)
        return {'series': [{'title': 'MLS WiFi', 'data': data[0]}]}

    @view_config(renderer='templates/stats.pt',
                 route_name="stats", http_cache=3600)
    def stats_view(self):
        redis_client = self.request.registry.redis_client
        cache_key = CACHE_KEYS['stats']
        cached = redis_client.get(cache_key)
        if cached:
            data = loads(cached)
        else:
            session = self.request.db_slave_session
            data = {
                'leaders': [],
                'metrics1': [],
                'metrics2': [],
            }
            metrics = global_stats(session)
            metric_names = [
                ('unique_cell', 'MLS Cells'),
                ('unique_ocid_cell', 'OpenCellID Cells'),
                ('cell', 'MLS Cell Observations'),
                ('unique_wifi', 'Wifi Networks'),
                ('wifi', 'Wifi Observations'),
            ]
            for mid, name in metric_names[:3]:
                data['metrics1'].append({'name': name, 'value': metrics[mid]})
            for mid, name in metric_names[3:]:
                data['metrics2'].append({'name': name, 'value': metrics[mid]})
            redis_client.set(cache_key, dumps(data), ex=3600)

        result = {'page_title': 'Statistics'}
        result.update(data)
        return result

    @view_config(renderer='templates/stats_countries.pt',
                 route_name="stats_countries", http_cache=3600)
    def stats_countries_view(self):
        redis_client = self.request.registry.redis_client
        cache_key = CACHE_KEYS['stats_countries']
        cached = redis_client.get(cache_key)
        if cached:
            data = loads(cached)
        else:
            session = self.request.db_slave_session
            data = countries(session)
            redis_client.set(cache_key, dumps(data), ex=3600)

        return {'page_title': 'Cell Statistics', 'metrics': data}


def favicon_view(request):
    return FileResponse(FAVICON_PATH, request=request)


def touchicon_view(request):
    return FileResponse(TOUCHICON_PATH, request=request)


_robots_response = Response(
    content_type='text/plain',
    body="User-agent: *\n"
         "Disallow: /leaders\n"
         "Disallow: /static/\n"
         "Disallow: /v1/\n"
)


def robotstxt_view(context, request):
    return _robots_response
