import argparse
import csv
import datetime
import sys

from colander import iso8601

from ichnaea import config
from ichnaea.db import Database
from ichnaea.decimaljson import to_precise_int
from ichnaea.models import normalize_wifi_key
from ichnaea.service.submit.tasks import (
    process_mapstat,
    process_measure,
)
from ichnaea.service.submit.utils import process_score


def load_file(session, source_file, batch_size=1000, userid=None):
    utcnow = datetime.datetime.utcnow().replace(tzinfo=iso8601.UTC)
    utcmin = utcnow - datetime.timedelta(120)

    with open(source_file, 'r') as fd:
        reader = csv.reader(fd, delimiter='\t', quotechar=None)

        counter = 0
        measures = []
        positions = []
        for fields in reader:
            try:
                time = int(fields[0])
                if time == 0:  # pragma: no cover
                    # unknown time gets an old date
                    time = utcmin
                else:
                    # convert from unixtime to utc
                    time = datetime.datetime.utcfromtimestamp(time)

                key = normalize_wifi_key(str(fields[5]))
                if key == '000000000000':  # pragma: no cover
                    continue

                lat = fields[1]
                lon = fields[2]
                signal = int(fields[3])
                channel = int(fields[4])
                wifi = dict(
                    key=key,
                    channel=channel,
                    signal=signal,
                )
                data = dict(
                    lat=lat,
                    lon=lon,
                    time=time,
                    accuracy=0,
                    altitude=0,
                    altitude_accuracy=0,
                    radio='',
                    cell=(),
                    wifi=[wifi],
                )
            except (ValueError, IndexError):
                continue
            # side effect, schedules async tasks
            measure = process_measure(data, utcnow, session, userid=userid)
            measures.append(measure)
            positions.append({
                'lat': to_precise_int(lat),
                'lon': to_precise_int(lon),
            })
            counter += 1

            # flush every batch_size records
            if counter % batch_size == 0:
                process_mapstat(positions, session, userid=userid)
                session.flush()
                measures = []
                positions = []
                print('Added %s records.' % counter)

    # process the remaining measures
    if positions:
        process_mapstat(positions, session, userid=userid)
        print('Added %s records.' % len(positions))

    if userid is not None:
        process_score(userid, counter, session)

    session.flush()
    return counter


def main(argv, _db_master=None):
    parser = argparse.ArgumentParser(
        prog=argv[0], description='Location Importer')

    parser.add_argument('source', help="The source file.")
    parser.add_argument('--userid', default=None,
                        help='Internal userid for attribution.')

    args = parser.parse_args(argv[1:])
    userid = None
    if args.userid is not None:
        userid = int(args.userid)

    settings = config().get_map('ichnaea')

    # configure databases incl. test override hooks
    if _db_master is None:
        db = Database(
            settings['db_master'],
            socket=settings.get('db_master_socket'),
            create=False,
        )
    else:
        db = _db_master
    session = db.session()
    added = load_file(session, args.source, userid=userid)
    print('Added a total of %s records.' % added)
    session.commit()
    return added


def console_entry():  # pragma: no cover
    main(sys.argv)
