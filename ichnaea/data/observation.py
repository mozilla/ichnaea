from collections import defaultdict

from sqlalchemy.orm import load_only

from ichnaea.constants import (
    PERMANENT_BLACKLIST_THRESHOLD,
    TEMPORARY_BLACKLIST_DURATION,
)
from ichnaea.data.report import process_score
from ichnaea.data.schema import ValidCellKeySchema
from ichnaea.models import (
    Cell,
    CellBlacklist,
    CellObservation,
    Wifi,
    WifiBlacklist,
    WifiObservation,
)
from ichnaea import util


class ObservationQueue(object):

    def __init__(self, task, session, utcnow=None, max_observations=11000):
        self.task = task
        self.session = session
        self.stats_client = task.stats_client
        self.max_observations = max_observations
        if utcnow is None:
            utcnow = util.utcnow()
        self.utcnow = utcnow

    def insert(self, entries, userid=None):

        all_observations = []
        dropped_blacklisted = 0
        dropped_malformed = 0
        dropped_overflow = 0
        stats_client = self.stats_client
        new_stations = 0

        # Process entries and group by validated station key
        station_observations = defaultdict(list)
        for entry in entries:
            entry['created'] = self.utcnow
            obs = self.observation_model.create(entry)

            if not obs:
                dropped_malformed += 1
                continue

            station_observations[obs.hashkey()].append(obs)

        # Process observations one station at a time
        for key, observations in station_observations.items():

            first_blacklisted = None
            incomplete = False
            is_new_station = False

            # Figure out how much space is left for this station.
            free = self.available_station_space(key)
            if free is None:
                is_new_station = True
                free = self.max_observations

            if is_new_station:
                # Drop observations for blacklisted stations.
                blacklisted, first_blacklisted = self.blacklisted_station(key)
                if blacklisted:
                    dropped_blacklisted += len(observations)
                    continue

                incomplete = self.incomplete_observation(key)
                if not incomplete:
                    # We discovered an actual new complete station.
                    new_stations += 1

            # Accept observations up to input-throttling limit, then drop.
            num = 0
            for obs in observations:
                if free <= 0:
                    dropped_overflow += 1
                    continue
                all_observations.append(obs)
                free -= 1
                num += 1

            # Accept incomplete observations, just don't make stations for them.
            # (station creation is a side effect of count-updating)
            if not incomplete and num > 0:
                self.create_or_update_station(key, num, first_blacklisted)

        # Credit the user with discovering any new stations.
        if userid is not None and new_stations > 0:
            process_score(self.session, userid, new_stations,
                          'new_' + self.station_type)

        if dropped_blacklisted != 0:
            stats_client.incr(
                'items.dropped.%s_ingress_blacklisted' % self.station_type,
                count=dropped_blacklisted)

        if dropped_malformed != 0:
            stats_client.incr(
                'items.dropped.%s_ingress_malformed' % self.station_type,
                count=dropped_malformed)

        if dropped_overflow != 0:
            stats_client.incr(
                'items.dropped.%s_ingress_overflow' % self.station_type,
                count=dropped_overflow)

        stats_client.incr(
            'items.inserted.%s_observations' % self.station_type,
            count=len(all_observations))

        self.session.add_all(all_observations)
        return len(all_observations)

    def available_station_space(self, key):
        # check if there's space for new observations within per-station
        # maximum old observations are gradually backed up, so this is an
        # intake-rate limit
        query = (self.station_model.querykey(self.session, key)
                                   .options(load_only('total_measures')))
        curr = query.first()

        if curr is not None:
            return self.max_observations - curr.total_measures

        # Return None to signal no station record was found.
        return None

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
        """
        Certain incomplete observations we want to store in the database
        even though they should not lead to the creation of a station
        entry; these are cell observations with a missing value for
        LAC and/or CID, and will be inferred from neighboring cells.
        """
        if self.station_type == 'cell':
            schema = ValidCellKeySchema()
            for field in ('radio', 'lac', 'cid'):
                if getattr(key, field, None) == schema.fields[field].missing:
                    return True
        return False

    def create_or_update_station(self, key, num, first_blacklisted):
        """
        Creates a station or updates its new/total_measures counts to reflect
        recently-received observations.
        """
        query = self.station_model.querykey(self.session, key)
        station = query.first()

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
                             'total_measures = total_measures + %s' % (num, num)
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


class WifiObservationQueue(ObservationQueue):

    station_type = "wifi"
    station_model = Wifi
    observation_model = WifiObservation
    blacklist_model = WifiBlacklist
