from collections import defaultdict

from sqlalchemy.orm import load_only

from ichnaea.constants import (
    PERMANENT_BLACKLIST_THRESHOLD,
    TEMPORARY_BLACKLIST_DURATION,
)
from ichnaea.customjson import decode_radio_dict
from ichnaea.data.base import DataTask
from ichnaea.data.report import process_score
from ichnaea.models import (
    Cell,
    CellBlacklist,
    CellObservation,
    ValidCellKeySchema,
    Wifi,
    WifiBlacklist,
    WifiObservation,
)
from ichnaea import util


class ObservationQueue(DataTask):

    def __init__(self, task, session, utcnow=None):
        DataTask.__init__(self, task, session)
        if utcnow is None:
            utcnow = util.utcnow()
        self.utcnow = utcnow

    def stat_count(self, action, what, count):
        if count != 0:
            self.stats_client.incr(
                'items.{action}.{station_type}_{what}'.format(
                    action=action, station_type=self.station_type, what=what),
                count)

    def emit_stats(self, added, dropped):
        self.stat_count('inserted', 'observations', added)
        for name, count in dropped.items():
            self.stat_count('dropped', 'ingress_' + name, dropped[name])

    def pre_process_entry(self, entry):
        entry['created'] = self.utcnow

    def insert(self, entries, userid=None):
        all_observations = []
        drop_counter = defaultdict(int)
        new_stations = 0

        # Process entries and group by validated station key
        station_observations = defaultdict(list)
        for entry in entries:
            self.pre_process_entry(entry)

            obs = self.observation_model.create(**entry)
            if not obs:
                drop_counter['malformed'] += 1
                continue

            station_observations[obs.hashkey()].append(obs)

        # Process observations one station at a time
        for key, observations in station_observations.items():
            first_blacklisted = None
            incomplete = False
            station = self.station_model.querykey(self.session, key).first()

            if station is None:
                # Drop observations for blacklisted stations.
                blacklisted, first_blacklisted = self.blacklisted_station(key)
                if blacklisted:
                    drop_counter['blacklisted'] += len(observations)
                    continue

                incomplete = self.incomplete_observation(key)
                if not incomplete:
                    # We discovered an actual new complete station.
                    new_stations += 1

            # Accept all observations
            all_observations.extend(observations)
            num = len(observations)

            # Accept incomplete observations, just don't make stations for them
            # (station creation is a side effect of count-updating)
            if not incomplete and num > 0:
                self.create_or_update_station(station, key, num,
                                              first_blacklisted)

        # Credit the user with discovering any new stations.
        if userid is not None and new_stations > 0:
            process_score(self.session, userid, new_stations,
                          'new_' + self.station_type)

        added = len(all_observations)
        self.emit_stats(added, drop_counter)

        self.session.add_all(all_observations)
        return added

    def blacklisted_station(self, key):
        query = (self.blacklist_model.querykey(self.session, key)
                                     .options(load_only('count', 'time')))
        black = query.first()
        if black is not None:
            age = self.utcnow - black.time
            temp_blacklisted = age < TEMPORARY_BLACKLIST_DURATION
            perm_blacklisted = black.count >= PERMANENT_BLACKLIST_THRESHOLD
            if temp_blacklisted or perm_blacklisted:
                return (True, black.time)
            return (False, black.time)
        return (False, None)

    def incomplete_observation(self, key):
        return False

    def create_or_update_station(self, station, key, num,
                                 first_blacklisted):
        # Creates a station or updates its new/total_measures counts to
        # reflect recently-received observations.
        if station is not None:
            station.new_measures += num
            station.total_measures += num
        else:
            created = self.utcnow
            if first_blacklisted:
                # if the station did previously exist, retain at least the
                # time it was first put on a blacklist as the creation date
                created = first_blacklisted
            stmt = self.station_model.__table__.insert(
                on_duplicate='new_measures = new_measures + %s, '
                             'total_measures = total_measures + %s' % (
                                 num, num)
            ).values(
                created=created,
                modified=self.utcnow,
                range=0,
                new_measures=num,
                total_measures=num,
                **key.__dict__)
            self.session.execute(stmt)


class CellObservationQueue(ObservationQueue):

    station_type = "cell"
    station_model = Cell
    observation_model = CellObservation
    blacklist_model = CellBlacklist

    def pre_process_entry(self, entry):
        ObservationQueue.pre_process_entry(self, entry)
        decode_radio_dict(entry)

    def incomplete_observation(self, key):
        # We want to store certain incomplete observations in the database
        # even though they should not lead to the creation of a station
        # entry; these are cell observations with a missing value for
        # LAC and/or CID, and will be inferred from neighboring cells.
        schema = ValidCellKeySchema()
        for field in ('radio', 'lac', 'cid'):
            if getattr(key, field, None) == schema.fields[field].missing:
                return True
        return False


class WifiObservationQueue(ObservationQueue):

    station_type = "wifi"
    station_model = Wifi
    observation_model = WifiObservation
    blacklist_model = WifiBlacklist
