from datetime import timedelta

from sqlalchemy import func

from ichnaea.models import (
    BlueShard,
    CellArea,
    RegionStat,
    Stat,
    StatCounter,
    StatKey,
    WifiShard,
)
from ichnaea import util


class StatCounterUpdater(object):

    def __init__(self, task):
        self.task = task
        self.today = util.utcnow().date()
        self.yesterday = util.utcnow().date() - timedelta(days=1)

    def __call__(self):
        with self.task.redis_pipeline() as pipe:
            with self.task.db_session() as session:
                for stat_key in StatKey:
                    self.update_key(session, pipe, stat_key, self.yesterday)
                    self.update_key(session, pipe, stat_key, self.today)

    def update_key(self, session, pipe, stat_key, day):
        # Get value for the given day from Redis.
        stat_counter = StatCounter(stat_key, day)
        value = stat_counter.get(self.task.redis_client)

        # Get value for the given day from the database.
        stat = (session.query(Stat)
                       .filter((Stat.key == stat_key),
                               (Stat.time == day))).first()
        if stat is not None:
            # If the day already has an entry, update it.
            if value:
                stat.value += value
                stat_counter.decr(pipe, value)
        else:
            # Get the most recent value for the stat from the database.
            before = (session.query(Stat)
                             .filter((Stat.key == stat_key),
                                     (Stat.time < day))
                             .order_by(Stat.time.desc())
                             .limit(1)).first()
            old_value = 0
            if before:
                old_value = before.value

            # Insert a new stat value.
            stmt = Stat.__table__.insert(
                mysql_on_duplicate='value = value + %s' % value
            ).values(key=stat_key, time=day, value=old_value + value)
            session.execute(stmt)
            stat_counter.decr(pipe, value)


class StatRegion(object):

    def __init__(self, task):
        self.task = task

    def __call__(self):
        with self.task.db_session() as session:
            self._update_stats(session)

    def _update_stats(self, session):
        cells = (session.query(CellArea.region,
                               CellArea.radio,
                               func.sum(CellArea.num_cells))
                        .filter(CellArea.region.isnot(None))
                        .group_by(CellArea.region, CellArea.radio)).all()

        default = {'gsm': 0, 'wcdma': 0, 'lte': 0, 'blue': 0, 'wifi': 0}
        stats = {}
        for region, radio, num in cells:
            if region not in stats:
                stats[region] = default.copy()
            stats[region][radio.name] = int(num)

        for name, shard_model in (('blue', BlueShard), ('wifi', WifiShard)):
            for shard in shard_model.shards().values():
                stations = (session.query(shard.region, func.count())
                                   .filter(shard.region.isnot(None))
                                   .group_by(shard.region)).all()

                for region, num in stations:
                    if region not in stats:
                        stats[region] = default.copy()
                    stats[region][name] += int(num)

        if not stats:
            return

        region_stats = dict(session.query(RegionStat.region,
                                          RegionStat).all())
        for region, values in stats.items():
            if region in region_stats:
                region_stats[region].gsm = values['gsm']
                region_stats[region].wcdma = values['wcdma']
                region_stats[region].lte = values['lte']
                region_stats[region].blue = values['blue']
                region_stats[region].wifi = values['wifi']
            else:
                session.add(RegionStat(
                    region=region,
                    gsm=values['gsm'],
                    wcdma=values['wcdma'],
                    lte=values['lte'],
                    blue=values['blue'],
                    wifi=values['wifi'],
                ))

        obsolete_regions = list(set(region_stats.keys()) - set(stats.keys()))
        if obsolete_regions:
            (session.query(RegionStat)
                    .filter(RegionStat.region.in_(obsolete_regions))
             ).delete(synchronize_session=False)
