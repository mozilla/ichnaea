from sqlalchemy.exc import IntegrityError

from ichnaea.db import (
    Wifi,
    WifiBlacklist,
    WifiMeasure,
)
from ichnaea.decimaljson import decode_datetime
from ichnaea.tasks import DatabaseTask
from ichnaea.worker import celery


@celery.task(base=DatabaseTask, ignore_result=True)
def insert_wifi_measure(measure_data, entries):
    wifi_measures = []
    wifi_keys = set([e['key'] for e in entries])
    try:
        with insert_wifi_measure.db_session() as session:
            blacked = session.query(WifiBlacklist.key).filter(
                WifiBlacklist.key.in_(wifi_keys)).all()
            blacked = set([b[0] for b in blacked])
            wifis = session.query(Wifi.key, Wifi).filter(
                Wifi.key.in_(wifi_keys))
            wifis = dict(wifis.all())
            for entry in entries:
                wifi_key = entry['key']
                # skip blacklisted wifi AP's
                if wifi_key in blacked:
                    continue
                # convert frequency into channel numbers and remove frequency
                freq = entry.pop('frequency', 0)
                # if no explicit channel was given, calculate
                if freq and not entry['channel']:
                    if 2411 < freq < 2473:
                        # 2.4 GHz band
                        entry['channel'] = (freq - 2407) // 5
                    elif 5169 < freq < 5826:
                        # 5 GHz band
                        entry['channel'] = (freq - 5000) // 5
                wifi_measure = WifiMeasure(
                    measure_id=measure_data['id'],
                    created=decode_datetime(measure_data.get('created', '')),
                    lat=measure_data['lat'],
                    lon=measure_data['lon'],
                    time=decode_datetime(measure_data.get('time', '')),
                    accuracy=measure_data.get('accuracy', 0),
                    altitude=measure_data.get('altitude', 0),
                    altitude_accuracy=measure_data.get('altitude_accuracy', 0),
                    id=entry.get('id', None),
                    key=wifi_key,
                    channel=entry.get('channel', 0),
                    signal=entry.get('signal', 0),
                )
                wifi_measures.append(wifi_measure)
                # update new/total measure counts
                if wifi_key in wifis:
                    wifi = wifis[wifi_key]
                    wifi.new_measures = Wifi.new_measures + 1
                    wifi.total_measures = Wifi.total_measures + 1
                else:
                    wifis[wifi_key] = wifi = Wifi(
                        key=wifi_key, new_measures=1, total_measures=1)
                    session.add(wifi)

            session.add_all(wifi_measures)
            session.commit()
        return len(wifi_measures)
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise insert_wifi_measure.retry(exc=exc)
