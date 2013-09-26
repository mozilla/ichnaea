import datetime

from ichnaea.content.models import (
    Score,
    SCORE_TYPE,
)


def process_score(userid, points, session, key='location'):
    utcday = datetime.datetime.utcnow().date()
    key = SCORE_TYPE[key]
    rows = session.query(Score).filter(
        Score.userid == userid).filter(
        Score.key == key).filter(
        Score.time == utcday).limit(1).with_lockmode('update')
    old = rows.first()
    if old:
        # update score
        if isinstance(old.value, (int, long)):
            old.value = Score.value + points
        else:
            # already a sql expression
            old.value += points
    else:
        score = Score(userid=userid, key=key, time=utcday, value=points)
        session.add(score)
    return points
