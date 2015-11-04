from collections import defaultdict
import struct

from ichnaea.data.base import DataTask
from ichnaea.models.content import (
    DataMap,
    encode_datamap_grid,
)

MAPSTAT_STRUCT = struct.Struct('!ii')


def decode_mapstat_grid(value):
    return MAPSTAT_STRUCT.unpack(value)


def encode_mapstat_grid(lat, lon, scale=False):
    if scale:
        lat, lon = DataMap.scale(lat, lon)
    return MAPSTAT_STRUCT.pack(lat, lon)


class MapStatUpdater(DataTask):  # BBB

    def __init__(self, task, session, pipe):
        DataTask.__init__(self, task, session)
        self.pipe = pipe

    def __call__(self, batch=1000):
        map_queue = self.task.app.data_queues['update_mapstat']
        positions = map_queue.dequeue(batch=batch, json=False)
        if not positions:
            return 0

        grids = defaultdict(set)
        positions = set(positions)
        for position in positions:
            lat, lon = decode_mapstat_grid(position)
            grids[DataMap.shard_id(lat, lon)].add(
                encode_datamap_grid(lat, lon))

        for shard_id, values in grids.items():
            queue = self.task.app.data_queues['update_datamap_' + shard_id]
            queue.enqueue(list(values), json=False)

        if map_queue.enough_data(batch=batch):
            self.task.apply_async(
                kwargs={'batch': batch},
                countdown=2,
                expires=10)

        return len(positions)
