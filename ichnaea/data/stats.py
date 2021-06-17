from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.mysql import insert

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

            # Insert a new stat value, or increase if exists
            session.execute(
                insert(Stat.__table__)
                .values(key=stat_key, time=day, value=old_value + value)
                .on_duplicate_key_update(value=columns.value + value)
            )
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
                delete(table).where(table.c.time < two_years)
            )
        return deleted_rows


class StatRegion(object):
    """Populate the region_stat table, displayed at /stats/regions"""

    def __init__(self, task):
        self.task = task

    def __call__(self):
        with self.task.db_session(isolation_level="READ COMMITTED") as session:
            counts = self._gather_counts(session)
        if counts:
            with self.task.db_session() as session:
                self._update_stats(counts, session)

    def _gather_counts(self, session):
        """Count radio sources by region"""
        columns = CellArea.__table__.c
        cells = session.execute(
            select([columns.region, columns.radio, func.sum(columns.num_cells)])
            .where(columns.region.isnot(None))
            .group_by(columns.region, columns.radio)
        ).fetchall()

        default = {"gsm": 0, "wcdma": 0, "lte": 0, "blue": 0, "wifi": 0}
        counts = {}
        for region, radio, num in cells:
            if region not in counts:
                counts[region] = default.copy()
            counts[region][radio.name] = int(num)

        for name, shard_model in (("blue", BlueShard), ("wifi", WifiShard)):
            for shard in shard_model.shards().values():
                columns = shard.__table__.c
                stations = session.execute(
                    select([columns.region, func.count()])
                    .where(columns.region.isnot(None))
                    .group_by(columns.region)
                ).fetchall()

                for region, num in stations:
                    if region not in counts:
                        counts[region] = default.copy()
                    counts[region][name] += int(num)

        return counts

    def _update_stats(self, counts, session):
        """Update counts-by-region tables"""

        region_stats = dict(session.query(RegionStat.region, RegionStat).all())

        for region, values in counts.items():
            row = region_stats.pop(region, None)
            is_new = row is None
            if is_new:
                row = RegionStat(region=region)
            row.gsm = values["gsm"]
            row.wcdma = values["wcdma"]
            row.lte = values["lte"]
            row.blue = values["blue"]
            row.wifi = values["wifi"]
            if is_new:
                session.add(row)
        session.commit()

        # Delete any regions no longer represented by areas
        obsolete_regions = list(region_stats.keys())
        if obsolete_regions:
            session.execute(
                RegionStat.__table__.delete().where(
                    RegionStat.__table__.c.region.in_(obsolete_regions)
                )
            )
