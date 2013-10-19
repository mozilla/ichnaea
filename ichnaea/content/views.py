import datetime
import os

from pyramid.decorator import reify
from pyramid.events import NewResponse
from pyramid.events import subscriber
from pyramid.renderers import get_renderer
from pyramid.response import FileResponse
from pyramid.response import Response
from pyramid.view import view_config

from ichnaea.content.stats import (
    global_stats,
    histogram,
    leaders,
    map_csv,
    map_world_csv,
)


HERE = os.path.dirname(__file__)
FAVICON_PATH = os.path.join(HERE, 'static', 'favicon.ico')
# cache year lookup, needs server restart after new year :)
THIS_YEAR = unicode(datetime.datetime.utcnow().year)


def configure_content(config):
    config.add_view(favicon_view, name='favicon.ico',
                    http_cache=(86400, {'public': True}))
    config.add_view(robotstxt_view, name='robots.txt',
                    http_cache=(86400, {'public': True}))
    config.add_static_view(
        name='static', path='ichnaea.content:static', cache_max_age=3600)
    config.scan('ichnaea.content.views')


@subscriber(NewResponse)
def sts_header(event):
    response = event.response
    if response.content_type == 'text/html':
        response.headers.add('Strict-Transport-Security', 'max-age=2592000')


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

    @view_config(renderer='templates/homepage.pt', http_cache=300)
    def homepage_view(self):
        return {'page_title': 'Overview'}

    @view_config(renderer='templates/leaders.pt',
                 name="leaders", http_cache=300)
    def leaders_view(self):
        session = self.request.db_slave_session
        result = leaders(session)
        half = len(result) // 2 + len(result) % 2
        leaders1 = result[:half]
        leaders2 = result[half:]
        return {
            'page_title': 'Leaderboard',
            'leaders1': leaders1,
            'leaders2': leaders2,
        }

    @view_config(renderer='string', name="map.csv", http_cache=86400)
    def map_csv(self):
        session = self.request.db_slave_session
        return map_csv(session)

    @view_config(renderer='templates/map.pt', name="map", http_cache=300)
    def map_view(self):
        return {'page_title': 'Coverage Map'}

    @view_config(renderer='string', name="map_world.csv", http_cache=86400)
    def map_world_csv(self):
        session = self.request.db_slave_session
        return map_world_csv(session)

    @view_config(renderer='templates/map_world.pt', name="map_world",
                 http_cache=300)
    def map_world_view(self):
        return {'page_title': 'Coverage Map'}

    @view_config(renderer='json', name="stats_location.json", http_cache=86400)
    def stats_location_json(self):
        session = self.request.db_slave_session
        return {'histogram': histogram(session, 'location')}

    @view_config(
        renderer='json', name="stats_unique_cell.json", http_cache=86400)
    def stats_unique_cell_json(self):
        session = self.request.db_slave_session
        return {'histogram': histogram(session, 'unique_cell')}

    @view_config(
        renderer='json', name="stats_unique_wifi.json", http_cache=86400)
    def stats_unique_wifi_json(self):
        session = self.request.db_slave_session
        return {'histogram': histogram(session, 'unique_wifi')}

    @view_config(renderer='templates/stats.pt', name="stats", http_cache=86400)
    def stats_view(self):
        session = self.request.db_slave_session
        result = {'leaders': [], 'metrics': [], 'page_title': 'Statistics'}
        metrics = global_stats(session)
        metric_names = [
            ('location', 'Locations'),
            ('cell', 'Cells'),
            ('unique_cell', 'Unique Cells'),
            ('wifi', 'Wifi APs'),
            ('unique_wifi', 'Unique Wifi APs'),
        ]
        for mid, name in metric_names:
            result['metrics'].append({'name': name, 'value': metrics[mid]})
        return result


def favicon_view(request):
    return FileResponse(FAVICON_PATH, request=request)


_robots_response = Response(
    content_type='text/plain',
    body="User-agent: *\n"
         "Disallow: /leaders\n"
         "Disallow: /map\n"
         "Disallow: /map_world\n"
         "Disallow: /static/\n"
         "Disallow: /stats\n"
         "Disallow: /v1/\n"
)


def robotstxt_view(context, request):
    return _robots_response
