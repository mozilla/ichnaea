import csv
from cStringIO import StringIO
import math
import os

from pyramid.decorator import reify
from pyramid.events import NewResponse
from pyramid.events import subscriber
from pyramid.renderers import get_renderer
from pyramid.response import FileResponse
from pyramid.response import Response
from pyramid.view import view_config
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy.sql.expression import text

from ichnaea.db import CellMeasure
from ichnaea.db import Measure
from ichnaea.db import Score
from ichnaea.db import User
from ichnaea.db import WifiMeasure
from ichnaea.content.stats import histogram


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
        session = self.request.db_session
        select = text("select round(lat / 10000) as lat1, "
                      "round(lon / 10000) as lon1, count(*) as num "
                      "from measure group by lat1, lon1 having num > 10 "
                      "order by lat1, lon1")
        result = session.execute(select)
        rows = StringIO()
        csvwriter = csv.writer(rows)
        csvwriter.writerow(('lat', 'lon', 'value'))
        for lat, lon, num in result.fetchall():
            # use a logarithmic scale to give lesser used regions a chance
            num = int(math.ceil(math.log10(num)))
            csvwriter.writerow((int(lat) / 1000.0, int(lon) / 1000.0, num))
        return rows.getvalue()

    @view_config(renderer='templates/map.pt', name="map", http_cache=300)
    def map_view(self):
        return {'page_title': 'Coverage Map'}

    @view_config(renderer='json', name="stats.json", http_cache=300)
    def stats_json(self):
        return {'histogram': histogram(self.request.db_session)}

    @view_config(renderer='templates/stats.pt', name="stats", http_cache=300)
    def stats_view(self):
        session = self.request.db_session
        result = {'leaders': [], 'metrics': [], 'page_title': 'Statistics'}
        metrics = result['metrics']
        value = session.query(func.count(Measure.id)).first()[0]
        metrics.append({'name': 'Locations', 'value': value})
        value = session.query(func.count(CellMeasure.id)).first()[0]
        metrics.append({'name': 'Cells', 'value': value})
        value = session.query(
            CellMeasure.radio, CellMeasure.mcc, CellMeasure.mnc,
            CellMeasure.lac, CellMeasure.cid).\
            group_by(CellMeasure.radio, CellMeasure.mcc, CellMeasure.mnc,
                     CellMeasure.lac, CellMeasure.cid).count()
        metrics.append({'name': 'Unique Cells', 'value': value})
        value = session.query(func.count(WifiMeasure.id)).first()[0]
        metrics.append({'name': 'Wifi APs', 'value': value})
        value = session.query(func.count(distinct(WifiMeasure.key))).first()[0]
        metrics.append({'name': 'Unique Wifi APs', 'value': value})

        score_rows = session.query(
            Score).order_by(Score.value.desc()).limit(10).all()
        user_rows = session.query(User).all()
        users = {}
        for user in user_rows:
            users[user.id] = (user.token, user.nickname)

        for score in score_rows:
            token, nickname = users.get(score.id, ('', 'anonymous'))
            result['leaders'].append(
                {'token': token[:8], 'nickname': nickname, 'num': score.value})
        return result


def favicon_view(request):
    return FileResponse(FAVICON_PATH, request=request)


_robots_response = Response(content_type='text/plain',
                            body="User-agent: *\nDisallow: /\n")


def robotstxt_view(context, request):
    return _robots_response
