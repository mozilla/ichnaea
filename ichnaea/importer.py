import argparse
import csv
import datetime
import sys

from colander import iso8601

from ichnaea import config
from ichnaea.db import Database, _ArchivalModel, _VolatileModel
from ichnaea.models import (
    normalize_wifi_key,
    valid_wifi_pattern,
)
from ichnaea.service.submit.tasks import process_measures


def load_file(a_session, v_session, source_file, batch_size=100, userid=None):
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

                key = normalize_wifi_key(str(fields[1]))
                if not valid_wifi_pattern(key):  # pragma: no cover
                    continue

                lat = fields[2]
                lon = fields[3]
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
                process_measures(items,
                                 archival_session=a_session,
                                 volatile_session=v_session,
                                 userid=userid)
                items = []
                a_session.flush()
                v_session.flush()
                print('Added %s records.' % counter)

    # process the remaining items
    process_measures(items,
                     archival_session=a_session,
                     volatile_session=v_session,
                     userid=userid)
    print('Added %s records.' % counter)

    a_session.flush()
    v_session.flush()
    return counter


def main(argv, _archival_db=None, _volatile_db=None):
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
    if _archival_db is None:
        a_db = Database(
            settings['archival_db_url'],
            _ArchivalModel,
            socket=settings.get('archival_db_socket'),
            create=False,
        )
    else:
        a_db = _archival_db

    # configure databases incl. test override hooks
    if _volatile_db is None:
        v_db = Database(
            settings['volatile_db_url'],
            _VolatileModel,
            socket=settings.get('volatile_db_socket'),
            create=False,
        )
    else:
        v_db = _volatile_db

    a_session = a_db.session()
    v_session = v_db.session()
    added = load_file(a_session, v_session, args.source, userid=userid)
    print('Added a total of %s records.' % added)
    a_session.commit()
    v_session.commit()
    return added


def console_entry():  # pragma: no cover
    main(sys.argv)
