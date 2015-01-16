"""
This script is used to process imports of user contributed data into
the Ichnaea database.

The fileformat is a custom TSV format based on the code found at:
https://github.com/cpeterso/stumbler-tsv
"""

import argparse
import csv
import datetime
import sys

from colander import Invalid, String

from ichnaea.app_config import read_config
from ichnaea.data.schema import WifiKeyNode
from ichnaea.data.tasks import process_measures
from ichnaea.db import Database
from ichnaea.logging import (
    configure_heka,
    configure_stats,
)
from ichnaea import util


def load_file(session, source_file, batch_size=1000, userid=None):
    utcnow = util.utcnow()
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

                try:
                    key = WifiKeyNode(String()).deserialize(str(fields[1]))
                except Invalid:
                    continue

                lat = float(fields[2])
                lon = float(fields[3])
                if lat == 0.0 and lon == 0.0:  # pragma: no cover
                    continue
                accuracy = int(float(fields[4]))
                altitude = int(float(fields[5]))
                altitude_accuracy = int(float(fields[6]))
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

                    # not sure if the importer has an actual file
                    # specification anywhere
                    heading=-255,
                    speed=-255,
                )
            except (ValueError, IndexError):  # pragma: no cover
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


def main(argv, _db_master=None, _heka_client=None, _stats_client=None):
    parser = argparse.ArgumentParser(
        prog=argv[0], description='Location Importer')

    parser.add_argument('source', help="The source file.")
    parser.add_argument('--userid', default=None,
                        help='Internal userid for attribution.')

    args = parser.parse_args(argv[1:])
    userid = None
    if args.userid is not None:
        userid = int(args.userid)

    conf = read_config()
    settings = conf.get_map('ichnaea')
    configure_heka(conf.filename, _heka_client=_heka_client)
    configure_stats(conf.get('ichnaea', 'statsd_host'), _client=_stats_client)

    # configure databases incl. test override hooks
    if _db_master is None:  # pragma: no cover
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
