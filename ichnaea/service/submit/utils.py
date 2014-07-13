from ichnaea.content.models import (
    Score,
    SCORE_TYPE,
)
from ichnaea import util


def process_score(userid, points, session, key='location'):
    utcday = util.utcnow().date()
    stmt = Score.__table__.insert(
        on_duplicate='value = value + %s' % int(points)).values(
        userid=userid, key=SCORE_TYPE[key], time=utcday, value=points)
    session.execute(stmt)
    return points
