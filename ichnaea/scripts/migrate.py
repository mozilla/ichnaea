"""
Manual migration script to move networks from old single wifi table
to new sharded wifi table structure.
"""
from collections import defaultdict
import sys
import time

from ichnaea.config import read_config
from ichnaea.db import (
    configure_db,
    db_worker_session,
)
from ichnaea.models.wifi import (
    Wifi,
    WifiShard,
)


def migrate(db, batch=1000):
    added = 0
    deleted = 0
    skipped = 0
    with db_worker_session(db, commit=True) as session:
        old_wifis = (session.query(Wifi)
                            .order_by(Wifi.id.desc())
                            .limit(batch)).all()
        sharded = defaultdict(list)
        for old_wifi in old_wifis:
            shard = WifiShard.shard_model(old_wifi.key)
            sharded[shard].append(shard(
                mac=old_wifi.key,
                created=old_wifi.created,
                modified=old_wifi.modified,
                lat=old_wifi.lat,
                lon=old_wifi.lon,
                max_lat=old_wifi.max_lat,
                min_lat=old_wifi.min_lat,
                max_lon=old_wifi.max_lon,
                min_lon=old_wifi.min_lon,
                radius=old_wifi.range,
                samples=old_wifi.total_measures,
            ))

        moved_wifis = set()
        for shard, wifis in sharded.items():
            shard_macs = set([wifi.mac for wifi in wifis])
            existing = (session.query(shard.mac)
                               .filter(shard.mac.in_(list(shard_macs)))).all()
            existing = set([e.mac for e in existing])
            for wifi in wifis:
                if wifi.mac not in existing:
                    moved_wifis.add(wifi.mac)
                    session.add(wifi)
                    added += 1
                else:
                    skipped += 1

        if moved_wifis:
            query = (session.query(Wifi)
                            .filter(Wifi.key.in_(list(moved_wifis))))
            deleted = query.delete(synchronize_session=False)
        else:
            deleted = 0
    return (added, deleted, skipped)


def main(db, repeat=1, batch=1000):
    for i in range(repeat):
        start = time.time()
        print('Start: %s' % time.strftime('%H:%m', time.gmtime(start)))
        added, deleted, skipped = migrate(db, batch=batch)
        end = int((time.time() - start) * 1000)
        print('Added: %s, Deleted: %s, Skipped: %s' % (
            added, deleted, skipped))
        print('Took: %s ms\n' % end)
    print('End')


if __name__ == '__main__':
    argv = sys.argv
    batch = 1000
    repeat = 1
    if len(argv) > 1:
        batch = int(argv[-1])
    if len(argv) > 2:
        repeat = int(argv[-2])
    app_config = read_config()
    db = configure_db(app_config.get('database', 'rw_url'))
    main(db, repeat=repeat, batch=batch)
