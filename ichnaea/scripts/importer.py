import argparse
import csv
import datetime
import sys

from colander import iso8601

from ichnaea import config
from ichnaea.db import Database
from ichnaea.models import (
    normalized_wifi_key,
    valid_wifi_pattern,
)
from ichnaea.service.submit.tasks import process_measures


def load_file(session, source_file, batch_size=100, userid=None):
    utcnow = datetime.datetime.utcnow().replace(tzinfo=iso8601.UTC)
    utcmin = utcnow - datetime.timedelta(120)

    with open(source_file, 'r') as fd:
        reader = csv.reader(fd, delimiter='\t', quotechar=None)

        counter = 0
        items = []
        for fields in reader:
            try:
                time = int(fields[0])
                if time == 0:  # pragma: no cover
                    # unknown time gets an old date
                    time = utcmin
                else:
                    # convert from unixtime to utc
                    time = datetime.datetime.utcfromtimestamp(time)

                key = normalized_wifi_key(str(fields[1]))
                if not valid_wifi_pattern(key):  # pragma: no cover
                    continue

                lat = float(fields[2])
                lon = float(fields[3])
                accuracy = int(fields[4])
                altitude = int(fields[5])
                altitude_accuracy = int(fields[6])
                channel = int(fields[7])
                signal = int(fields[8])

                wifi = dict(
                    key=key,
                    channel=channel,
                    signal=signal,
                )
                data = dict(
                    lat=lat,
                    lon=lon,
                    time=time,
                    accuracy=accuracy,
                    altitude=altitude,
                    altitude_accuracy=altitude_accuracy,
                    radio='',
                    cell=(),
                    wifi=[wifi],
                )
            except (ValueError, IndexError):
                continue

            items.append(data)
            counter += 1

            # flush every batch_size records
            if counter % batch_size == 0:
                process_measures(items, session, userid=userid)
                items = []
                session.flush()
                print('Added %s records.' % counter)

    # process the remaining items
    process_measures(items, session, userid=userid)
    print('Added %s records.' % counter)

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
        db = Database(settings['db_master'])
    else:
        db = _db_master
    session = db.session()
    added = load_file(session, args.source, userid=userid)
    print('Added a total of %s records.' % added)
    session.commit()
    return added


def console_entry():  # pragma: no cover
    main(sys.argv)
