import operator
import os

from pyramid.renderers import get_renderer
from pyramid.response import FileResponse
from pyramid.response import Response
from pyramid.view import view_config
from sqlalchemy import func

from ichnaea.db import Measure
from ichnaea.db import User


HERE = os.path.dirname(__file__)
FAVICON_PATH = os.path.join(HERE, 'static', 'favicon.ico')


def configure_content(config):
    config.add_route('homepage', '/')
    config.add_route('map', '/map')
    config.add_route('stats', '/stats')

    config.add_route('favicon', '/favicon.ico')
    config.add_view(favicon_view, route_name='favicon', http_cache=86400)

    config.add_route('robots', '/robots.txt')
    config.add_view(robotstxt_view, route_name='robots', http_cache=86400)

    config.add_static_view(
        name='static', path='ichnaea.content:static', cache_max_age=3600)

    config.scan('ichnaea.content.views')


def get_base_macros():
    base_macros = get_renderer('templates/base_macros.pt').implementation()
    return base_macros


@view_config(route_name='homepage', renderer='templates/homepage.pt')
def homepage_view(request):
    return {'base_macros': get_base_macros()}


@view_config(route_name='map', renderer='templates/map.pt')
def map_view(request):
    return {'base_macros': get_base_macros()}


@view_config(route_name='stats', renderer='templates/stats.pt')
def stats_view(request):
    session = request.database.session()
    base_macros = get_base_macros()
    result = {'leaders': [], 'base_macros': base_macros}
    result['total_measures'] = session.query(Measure).count()

    rows = session.query(Measure.token, func.count(Measure.id)).\
        filter(Measure.token != "").\
        group_by(Measure.token).all()
    users = session.query(User).all()
    user_map = {}
    for user in users:
        user_map[user.token] = user.nickname

    for token, num in sorted(rows, key=operator.itemgetter(1), reverse=True):
        nickname = user_map.get(token, 'anonymous')
        result['leaders'].append(
            {'token': token[:8], 'nickname': nickname, 'num': num})
    return result


def favicon_view(request):
    return FileResponse(FAVICON_PATH, request=request)


_robots_response = Response(content_type='text/plain',
                            body="User-agent: *\nDisallow: /\n")


def robotstxt_view(context, request):
    return _robots_response
