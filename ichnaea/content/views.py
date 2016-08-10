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
TILES_PATTERN = '{z}/{x}/{y}.png'
HOMEPAGE_MAP_IMAGE = ('{scheme}://a.tiles.mapbox.com/v4/{map_id}'
                      '/0/0/0@2x.png?access_token={token}')


def configure_content(config):
    web_config = config.registry.settings.get('web', {})
    enabled = web_config.get('enabled', 'false')
    if enabled in ('false', '0'):
        config.add_view(empty_homepage_view,
                        http_cache=(86400, {'public': True}))
        return False

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

    # BBB: leaders/leaders_weekly redirect to new service
    config.add_route('leaders_weekly', '/leaders/weekly')
    config.add_route('leaders', '/leaders')
    config.add_route('stats_regions', '/stats/regions')
    config.add_route('stats', '/stats')

    config.scan('ichnaea.content.views')

    assets_url = config.registry.settings.get('assets', {}).get('url', '')
    if not assets_url.endswith('/'):
        assets_url = assets_url + '/'
    tiles_url = urlparse.urljoin(assets_url, 'tiles/' + TILES_PATTERN)

    result = urlparse.urlsplit(tiles_url)
    tiles = urlparse.urlunparse((result.scheme, result.netloc, '', '', '', ''))
    config.registry.csp = CSP_POLICY.format(base=CSP_BASE, tiles=tiles)

    config.registry.map_config = {
        'map_id_base': web_config.get('map_id_base', 'mapbox.streets'),
        'map_id_labels': web_config.get('map_id_labels', ''),
        'map_token': web_config.get('map_token', ''),
        'map_tiles_url': tiles_url,
    }
    return True


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
        scheme = urlparse.urlparse(self.request.url).scheme
        map_config = self.request.registry.map_config
        image_base_url = HOMEPAGE_MAP_IMAGE.format(
            scheme=scheme,
            map_id=map_config['map_id_base'],
            token=map_config['map_token'])
        image_url = map_config['map_tiles_url'].format(z=0, x=0, y='0@2x')
        return {
            'page_title': 'Overview',
            'map_image_base_url': image_base_url,
            'map_image_url': image_url,
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
                settings.get('assets', {}).get('bucket'),
                settings.get('assets', {}).get('url'),
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

    @view_config(route_name='leaders')
    def leaders_view(self):
        return HTTPMovedPermanently(
            location='https://location-leaderboard.services.mozilla.com')

    @view_config(route_name='leaders_weekly')
    def leaders_weekly_view(self):
        return HTTPMovedPermanently(
            location='https://location-leaderboard.services.mozilla.com')

    @view_config(renderer='templates/map.pt', name='map', http_cache=3600)
    def map_view(self):
        map_config = self.request.registry.map_config
        return {
            'page_title': 'Map',
            'map_id_base': map_config['map_id_base'],
            'map_id_labels': map_config['map_id_labels'],
            'map_tiles_url': map_config['map_tiles_url'],
            'map_token': map_config['map_token'],
        }

    @view_config(renderer='json', name='map.json', http_cache=3600)
    def map_json(self):
        tiles_url = self.request.registry.map_config.get('map_tiles_url', '')
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
            data = {'metrics1': [], 'metrics2': []}
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


_empty_homepage_response = Response(content_type='text/html', body='''\
<!DOCTYPE html><html><head>
<meta charset="UTF-8" />
<title>ichnaea</title>
</head><body>
<h1>It works!</h1>
<p>This is an installation of the open-source software
<a href="https://github.com/mozilla/ichnaea">Mozilla Ichnaea</a>.</p>
<p>Mozilla is not responsible for the operation or problems with
this specific instance, please contact the site operator first.</p>
</body></html>
''')


def empty_homepage_view(request):
    return _empty_homepage_response


def favicon_view(request):
    return FileResponse(FAVICON_PATH, request=request)


def touchicon_view(request):
    return FileResponse(TOUCHICON_PATH, request=request)


_robots_response = Response(content_type='text/plain', body='''\
User-agent: *
Disallow: /downloads
Disallow: /static/
Disallow: /v1/
Disallow: /v2/
Disallow: /__heartbeat__
Disallow: /__lbheartbeat__
Disallow: /__version__
''')


def robotstxt_view(context, request):
    return _robots_response
