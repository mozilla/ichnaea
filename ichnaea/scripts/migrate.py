"""
Manual migration script to move networks from old single wifi table
to new sharded wifi table structure.

Use via:

    $ ICHNAEA_CFG=/path/to/ini /path/to/vent/python migrate 0.1 100 1000
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


def migrate(db, batch=1000, order='asc'):
    added = 0
    blocked = 0
    deleted = 0
    updated = 0
    with db_worker_session(db, commit=True) as session:
        order_func = getattr(Wifi.id, order)
        old_wifis = (session.query(Wifi)
                            .order_by(order_func())
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
            shard_macs = [wifi.mac for wifi in wifis]
            existing = (session.query(shard)
                               .filter(shard.mac.in_(shard_macs))).all()
            existing = dict([(e.mac, e) for e in existing])
            for wifi in wifis:
                if wifi.mac not in existing:
                    moved_wifis.add(wifi.mac)
                    session.add(wifi)
                    added += 1
                else:
                    shard_wifi = existing.get(wifi.mac)
                    if shard_wifi.blocked():
                        moved_wifis.add(wifi.mac)
                        blocked += 1
                    else:
                        shard_wifi.created = min(
                            shard_wifi.created, wifi.created)
                        shard_wifi.modified = max(
                            shard_wifi.modified, wifi.modified)
                        shard_wifi.lat = wifi.lat
                        shard_wifi.lon = wifi.lon
                        shard_wifi.max_lat = wifi.max_lat
                        shard_wifi.min_lat = wifi.min_lat
                        shard_wifi.max_lon = wifi.max_lon
                        shard_wifi.min_lon = wifi.min_lon
                        shard_wifi.radius = wifi.radius
                        shard_wifi.samples = wifi.samples
                        moved_wifis.add(wifi.mac)
                        updated += 1

        if moved_wifis:
            query = (session.query(Wifi)
                            .filter(Wifi.key.in_(list(moved_wifis))))
            deleted = query.delete(synchronize_session=False)
        else:
            deleted = 0
    return (added, deleted, updated, blocked)


def main(db, batch=1000, repeat=1, wait=0.3, order='asc'):
    for i in range(repeat):
        start = time.time()
        print('Start: %s - %s' % (
            i, time.strftime('%H:%m:%S', time.gmtime(start))))
        added, deleted, updated, blocked = migrate(
            db, batch=batch, order=order)
        end = int((time.time() - start) * 1000)
        print('Added: %s, Deleted: %s, Updated: %s, Blocked: %s' % (
            added, deleted, updated, blocked))
        print('Took: %s ms\n' % end)
        sys.stdout.flush()
        time.sleep(wait)
    print('End')


if __name__ == '__main__':
    argv = sys.argv
    batch = 1000
    repeat = 1
    wait = 0.3
    order = 'asc'
    if len(argv) > 1:
        batch = int(argv[-1])
    if len(argv) > 2:
        repeat = int(argv[-2])
    if len(argv) > 3:
        wait = float(argv[-3])
    if len(argv) > 4:
        order = str(argv[-4]).strip()
    app_config = read_config()
    db = configure_db(app_config.get('database', 'rw_url'))
    main(db, batch=batch, repeat=repeat, wait=wait, order=order)
