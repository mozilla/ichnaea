import operator
import os

from pyramid.decorator import reify
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
    config.add_view(favicon_view, name='favicon.ico', http_cache=86400)
    config.add_view(robotstxt_view, name='robots.txt', http_cache=86400)

    config.add_static_view(
        name='static', path='ichnaea.content:static', cache_max_age=3600)

    config.scan('ichnaea.content.views')


class Layouts(object):

    @reify
    def base_template(self):
        renderer = get_renderer("templates/base.pt")
        return renderer.implementation().macros['layout']

    @reify
    def base_macros(self):
        renderer = get_renderer("templates/base_macros.pt")
        return renderer.implementation().macros


class ContentViews(Layouts):

    def __init__(self, request):
        self.request = request

    @view_config(renderer='templates/homepage.pt')
    def homepage_view(self):
        return {'page_title': 'Overview'}

    @view_config(renderer='templates/map.pt', name="map")
    def map_view(self):
        return {'page_title': 'Coverage Map'}

    @view_config(renderer='templates/stats.pt', name="stats")
    def stats_view(self):
        session = self.request.database.session()
        result = {'leaders': [], 'page_title': 'Statistics'}
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
