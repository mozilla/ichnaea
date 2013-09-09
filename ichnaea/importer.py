import argparse
import csv
import datetime
import sys

from colander import iso8601
from konfig import Config

from ichnaea.db import Database
from ichnaea.submit import process_measure


def _int(value):
    try:
        return int(value)
    except ValueError:
        return 0


def load_file(session, source_file, batch_size=10000):
    utcnow = datetime.datetime.utcnow().replace(tzinfo=iso8601.UTC)
    utcmin = utcnow - datetime.timedelta(120)

    with open(source_file, 'r') as fd:
        reader = csv.reader(fd, delimiter='\t', quotechar=None)
        session_objects = []
        counter = 0

        for fields in reader:
            try:
                time = int(fields[0])
                if time == 0:
                    # unknown time gets an old date
                    time = utcmin
                else:
                    # convert from unixtime to utc
                    time = datetime.datetime.utcfromtimestamp(time)
                key = str(fields[1])
                if len(key) != 40:  # pragma: no cover
                    print "too short key: %s" % key
                    continue
                lat = fields[2]
                lon = fields[3]
                signal = int(fields[4])
                if signal > 0 or signal < -140:
                    signal = -140
                channel = int(fields[5])
                if channel < 0:
                    channel = 0
                ssid = str(fields[6])
                if ssid == '00:00:00:00:00:00':
                    continue
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
            session_objects.extend(process_measure(data, utcnow, session))

            # flush every 1000 new records
            counter += 1
            if counter % batch_size == 0:
                session.add_all(session_objects)
                session.flush()
                print('Added %s records.' % counter)
                session_objects = []

    # add the rest
    session.add_all(session_objects)
    session.flush()
    return counter


def main(argv):
    parser = argparse.ArgumentParser(
        prog=argv[0], description='Location Importer')

    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('config', help="config file")
    parser.add_argument('source', help="source file")
    args = parser.parse_args(argv[1:])
    settings = Config(args.config).get_map('ichnaea')
    db = Database(
        settings['db_master'],
        socket=settings.get('db_master_socket'),
        create=False,
    )
    session = db.session()
    added = load_file(session, args.source)
    print('Added %s records.' % added)
    if args.dry_run:
        session.rollback()
    else:  # pragma: no cover
        session.commit()
    return added


def console_entry():  # pragma: no cover
    main(sys.argv)
