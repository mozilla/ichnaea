import datetime
import os
import urlparse

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


HERE = os.path.dirname(__file__)
FAVICON_PATH = os.path.join(HERE, 'static', 'favicon.ico')
# cache year lookup, needs server restart after new year :)
THIS_YEAR = unicode(datetime.datetime.utcnow().year)

CSP_BASE = "'self' *.cdn.mozilla.net"
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
    elif not base_url.endswith('/'):
        base_url = base_url + '/'
    return urlparse.urljoin(base_url, 'tiles/' + TILES_PATTERN)


def configure_content(config):
    config.add_view(favicon_view, name='favicon.ico',
                    http_cache=(86400, {'public': True}))
    config.add_view(robotstxt_view, name='robots.txt',
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

    @view_config(renderer='templates/optout.pt',
                 name="optout", http_cache=3600)
    def optout_view(self):
        return {'page_title': 'Opt-Out'}

    @view_config(renderer='templates/privacy.pt',
                 name="privacy", http_cache=3600)
    def privacy_view(self):
        return {'page_title': 'Privacy Policy'}

    @view_config(renderer='templates/leaders.pt',
                 route_name="leaders", http_cache=3600)
    def leaders_view(self):
        session = self.request.db_slave_session
        result = list(enumerate(leaders(session)))
        result = [
            {
                'pos': l[0] + 1,
                'num': l[1]['num'],
                'nickname': l[1]['nickname'],
                'anchor': l[1]['nickname'],
            } for l in result]
        half = len(result) // 2 + len(result) % 2
        leaders1 = result[:half]
        leaders2 = result[half:]
        return {
            'page_title': 'Leaderboard',
            'leaders1': leaders1,
            'leaders2': leaders2,
        }

    @view_config(renderer='templates/leaders_weekly.pt',
                 route_name="leaders_weekly", http_cache=3600)
    def leaders_weekly_view(self):
        session = self.request.db_slave_session
        result = {
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
            result[name] = {
                'leaders1': value[:half],
                'leaders2': value[half:],
            }
        return {
            'page_title': 'Weekly Leaderboard',
            'scores': result,
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
        renderer='json', name="stats_unique_cell.json", http_cache=3600)
    def stats_unique_cell_json(self):
        session = self.request.db_slave_session
        return {'histogram': histogram(session, 'unique_cell')}

    @view_config(
        renderer='json', name="stats_unique_wifi.json", http_cache=3600)
    def stats_unique_wifi_json(self):
        session = self.request.db_slave_session
        return {'histogram': histogram(session, 'unique_wifi')}

    @view_config(renderer='templates/stats.pt',
                 route_name="stats", http_cache=3600)
    def stats_view(self):
        session = self.request.db_slave_session
        result = {
            'page_title': 'Statistics',
            'leaders': [],
            'metrics1': [],
            'metrics2': [],
        }
        metrics = global_stats(session)
        metric_names = [
            ('unique_cell', 'Unique Cells'),
            ('cell', 'Cell Observations'),
            ('unique_wifi', 'Unique Wifi Networks'),
            ('wifi', 'Wifi Observations'),
        ]
        for mid, name in metric_names[:2]:
            result['metrics1'].append({'name': name, 'value': metrics[mid]})
        for mid, name in metric_names[2:]:
            result['metrics2'].append({'name': name, 'value': metrics[mid]})
        return result

    @view_config(renderer='templates/stats_countries.pt',
                 route_name="stats_countries", http_cache=3600)
    def stats_countries_view(self):
        session = self.request.db_slave_session
        result = {'page_title': 'Cell Statistics'}
        result['metrics'] = countries(session)
        return result


def favicon_view(request):
    return FileResponse(FAVICON_PATH, request=request)


_robots_response = Response(
    content_type='text/plain',
    body="User-agent: *\n"
         "Disallow: /leaders\n"
         "Disallow: /static/\n"
         "Disallow: /v1/\n"
)


def robotstxt_view(context, request):
    return _robots_response
