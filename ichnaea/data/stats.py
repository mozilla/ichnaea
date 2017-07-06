from datetime import timedelta

from sqlalchemy import delete, func, select

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
                    session.flush()
                    self.update_key(session, pipe, stat_key, self.today)

    def update_key(self, session, pipe, stat_key, day):
        # Get value for the given day from Redis.
        stat_counter = StatCounter(stat_key, day)
        value = stat_counter.get(self.task.redis_client)

        # Get value for the given day from the database.
        columns = Stat.__table__.c
        stat = session.execute(
            select([columns.value])
            .where(columns.key == stat_key)
            .where(columns.time == day)
        ).fetchone()

        if stat is not None:
            # If the day already has an entry, update it.
            if value:
                session.execute(
                    Stat.__table__.update()
                    .where(columns.key == stat_key)
                    .where(columns.time == day)
                    .values(value=value + columns.value)
                )
                stat_counter.decr(pipe, value)
        else:
            # Get the most recent value for the stat from the database.
            before = session.execute(
                select([columns.value])
                .where(columns.key == stat_key)
                .where(columns.time < day)
                .order_by(columns.time.desc())
                .limit(1)
            ).fetchone()

            old_value = before.value if before else 0

            # Insert a new stat value.
            stmt = Stat.__table__.insert(
                mysql_on_duplicate='value = value + %s' % value
            ).values(key=stat_key, time=day, value=old_value + value)
            session.execute(stmt)
            stat_counter.decr(pipe, value)


class StatCleaner(object):

    def __init__(self, task):
        self.task = task

    def __call__(self):
        today = util.utcnow().date()
        two_years = today - timedelta(days=365 * 2)

        deleted_rows = 0
        with self.task.db_session() as session:
            table = Stat.__table__
            deleted_rows = session.execute(
                delete(table)
                .where(table.c.time < two_years)
            )
        return deleted_rows


class StatRegion(object):

    def __init__(self, task):
        self.task = task

    def __call__(self):
        with self.task.db_session() as session:
            self._update_stats(session)

    def _update_stats(self, session):
        columns = CellArea.__table__.c
        cells = session.execute(
            select([columns.region,
                    columns.radio,
                    func.sum(columns.num_cells)])
            .where(columns.region.isnot(None))
            .group_by(columns.region, columns.radio)
        ).fetchall()

        default = {'gsm': 0, 'wcdma': 0, 'lte': 0, 'blue': 0, 'wifi': 0}
        stats = {}
        for region, radio, num in cells:
            if region not in stats:
                stats[region] = default.copy()
            stats[region][radio.name] = int(num)

        for name, shard_model in (('blue', BlueShard), ('wifi', WifiShard)):
            for shard in shard_model.shards().values():
                columns = shard.__table__.c
                stations = session.execute(
                    select([columns.region, func.count()])
                    .where(columns.region.isnot(None))
                    .group_by(columns.region)
                ).fetchall()

                for region, num in stations:
                    if region not in stats:
                        stats[region] = default.copy()
                    stats[region][name] += int(num)

        if not stats:
            return

        rows = session.execute(
            select([RegionStat.__table__.c.region])
        ).fetchall()
        region_stats = set([row.region for row in rows])

        inserts = []
        updates = []
        for region, values in stats.items():
            data = {
                'region': region,
                'gsm': values['gsm'],
                'wcdma': values['wcdma'],
                'lte': values['lte'],
                'blue': values['blue'],
                'wifi': values['wifi'],
            }
            if region in region_stats:
                updates.append(data)
            else:
                inserts.append(data)

        if inserts:
            session.bulk_insert_mappings(RegionStat, inserts)

        if updates:
            session.bulk_update_mappings(RegionStat, updates)

        obsolete_regions = list(region_stats - set(stats.keys()))
        if obsolete_regions:
            session.execute(
                RegionStat.__table__.delete()
                .where(RegionStat.__table__.c.region.in_(obsolete_regions))
            )
