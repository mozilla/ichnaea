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
)


HERE = os.path.dirname(__file__)
FAVICON_PATH = os.path.join(HERE, 'static', 'favicon.ico')


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


class ContentViews(Layout):

    def __init__(self, request):
        self.request = request

    @view_config(renderer='templates/homepage.pt', http_cache=300)
    def homepage_view(self):
        return {'page_title': 'Overview'}

    @view_config(renderer='string', name="map.csv", http_cache=300)
    def map_csv(self):
        session = self.request.db_slave_session
        return map_csv(session)

    @view_config(renderer='templates/map.pt', name="map", http_cache=300)
    def map_view(self):
        return {'page_title': 'Coverage Map'}

    @view_config(renderer='json', name="stats.json", http_cache=300)
    def stats_json(self):
        session = self.request.db_slave_session
        return {'histogram': histogram(session)}

    @view_config(renderer='templates/stats.pt', name="stats", http_cache=300)
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
        result['leaders'] = leaders(session)
        return result


def favicon_view(request):
    return FileResponse(FAVICON_PATH, request=request)


_robots_response = Response(content_type='text/plain',
                            body="User-agent: *\nDisallow: /\n")


def robotstxt_view(context, request):
    return _robots_response
