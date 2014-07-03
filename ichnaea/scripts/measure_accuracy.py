#!/usr/bin/python2.7

# This is a script that tests ichnaea and/or other API-compatible
# location services for accuracy against a provided set of measurements.
#
# It requires 1 or 2 CSV files containing either cell or wifi measurements,
# each carrying a GPS-measured lat/lon, and with a common binary field
# 'report_id' shared between all rows asociated with the same measurement
# event. Any simple CSV dump of the wifi_measure and cell_measure tables in
# ichnaea should suffice, though you should probably use a small-ish
# subset, less than a few thousand rows.
#
# The script uses those measurements as _queries_ against a service
# specified by a nickname and URL (say,
# "MLS@https://location.services.mozilla.com/v1/geolocate?key=test") and
# plots the cumulative distribution function of the distances-from-GPS
# of each response from the location service. So if you get a short, steep
# plot your location service is very accurate; if you get a long, shallow
# plot your location service is very inaccurate.
#
# If you provide multiple --search or --geolocate URLs, multiple services
# will be plotted on the same graph. You can also select whether to plot
# measurements of several variants. Subsets can be taken where:
#
#    - both (wifi and cell) were measured (--both)
#    - both were measured, with cellid damaged (--both-lac)
#    - at least wifi was measured (--at-least-wifi)
#    - at least cells were measured (--at-least-cell)
#    - at least cells were measured, with cellid damaged (--at-least-lac)
#    - only wifi was measured (--only-wifi)
#    - only cells were measured (--only-cell)
#    - only cells were measured, with cellid damaged (--only-lac)
#
# If you supply multiple URLs and multiple variants, it will plot the cross
# product, so be careful! It's easy to make a graph too noisy to read.

import csv
import json
import requests
import argparse
import random
from collections import (
    defaultdict,
    namedtuple,
)
import math
import pylab
import re
import numpy
import datetime

EARTH_RADIUS = 6371


def distance(lat1, lon1, lat2, lon2):
    dLon = math.radians(lon2 - lon1)
    dLat = math.radians(lat2 - lat1)
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    a = math.sin(dLat / 2.0) * math.sin(dLat / 2.0) + \
        math.cos(lat1) * \
        math.cos(lat2) * \
        math.sin(dLon / 2.0) * \
        math.sin(dLon / 2.0)
    c = 2 * math.asin(min(1, math.sqrt(a)))
    d = EARTH_RADIUS * c
    return d


CellMeasure = namedtuple("CellMeasure",
                         "report_id lat lon mcc mnc lac cid radio")


WifiMeasure = namedtuple("WifiMeasure",
                         "report_id lat lon key channel")

TestQuery = namedtuple("TestQuery",
                       "lat lon cells wifis")

SEARCH_RADIO_TYPE = ['gsm', 'cdma', 'umts', 'lte']
GEOLOCATE_RADIO_TYPE = ['gsm', 'cdma', 'wcdma']


def coord(i):
    return float(i) / 10000000.0


def load_named_tuples_from_csv(nt, filename, typemap={'key': str,
                                                      'lat': coord,
                                                      'lon': coord}):
    csv_ix = {}
    ty_ix = {}
    rows = []
    with open(filename, 'rb') as f:
        reader = csv.reader(f, delimiter='\t')

        hdr = reader.next()
        for f in nt._fields:
            csv_ix[f] = hdr.index(f)
            ty_ix[f] = typemap.get(f, int)

        for row in reader:
            vs = [ty_ix[f](row[csv_ix[f]])
                  for f in nt._fields]
            rows.append(nt(*vs))

    return rows


def form_search_query(wifis, cells):

    d = {'radio': ''}

    if len(cells) != 0:
        d['cell'] = [
            {
                'radio': SEARCH_RADIO_TYPE[cell.radio],
                'mcc': cell.mcc,
                'mnc': cell.mnc,
                'lac': cell.lac,
                'cid': cell.cid
            }
            for cell in cells
        ]

    if len(wifis) != 0:
        d['wifi'] = [
            {
                'key': wifi.key,
                'channel': wifi.channel
            }
            for wifi in wifis
        ]

    return d


def form_geolocate_query(wifis, cells):

    d = {}

    if len(cells) != 0:

        radios = set([cell.radio for cell in cells])
        if len(radios) == 1:
            radio = radios.pop()
            if radio < len(GEOLOCATE_RADIO_TYPE):
                d['radioType'] = GEOLOCATE_RADIO_TYPE[radio]

        d['cellTowers'] = [
            {
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'locationAreaCode': cell.lac,
                'cellId': cell.cid
            }
            for cell in cells
        ]

    if len(wifis) != 0:
        d['wifiAccessPoints'] = [
            {
                'macAddress': ':'.join(re.findall('..', wifi.key)),
                'channel': wifi.channel
            }
            for wifi in wifis
        ]

    return d


def wifi_subset(wifis):
    if len(wifis) > 5:
        return random.sample(wifis, 5)
    else:
        return wifis


def geolocate_api(url, tq):
    q = form_geolocate_query(wifi_subset(tq.wifis), tq.cells)
    r = requests.post(url, data=json.dumps(q),
                      headers={'content-type': 'application/json'})
    if r.status_code == 200:
        j = r.json()
        if 'location' in j:
            loc = j['location']
            if 'lat' in loc and 'lng' in loc and 'accuracy' in j:
                dist = 1000.0 * distance(tq.lat, tq.lon,
                                         loc['lat'], loc['lng'])
                acc = j['accuracy']
                return (dist, acc)
    return None


def search_api(url, tq):
    q = form_search_query(wifi_subset(tq.wifis), tq.cells)
    r = requests.post(url, data=json.dumps(q),
                      headers={'content-type': 'application/json'})
    if r.status_code == 200:
        j = r.json()
        if 'lat' in j and 'lon' in j and 'accuracy' in j:
            dist = 1000.0 * distance(tq.lat, tq.lon, j['lat'], j['lon'])
            acc = j['accuracy']
            return (dist, acc)
    return None


def do_queries(url, api, tqs):

    distances = []
    accuracies = []

    for tq in tqs:
        retry = 5
        while retry > 0:
            r = api(url, tq)
            if r is not None:
                retry = 0
            else:
                print("error response (retrying)")
                retry -= 1

        if r is not None:
            (dist, acc) = r
            distances.append(dist)
            accuracies.append(acc)
            print("distance %.2fm, accuracy %.2fm" %
                  (dist, acc))
        else:
            print("persistent error response (ignored)")

    return (distances, accuracies)


def plot_distance_and_accuracy(da, percentiles, pct_lim, label):

    (dists, accuracies) = da
    if len(dists) == 0:
        print("no distances")
        return
    lim = numpy.percentile(dists, pct_lim)
    trimmed = [d for d in dists if d <= lim]

    pylab.hist(trimmed, bins=len(trimmed),
               normed=True,
               cumulative=True,
               histtype='step', label=label)

    percentiles[label] = {
        50: numpy.percentile(dists, 50),
        75: numpy.percentile(dists, 75),
        90: numpy.percentile(dists, 90),
        95: numpy.percentile(dists, 95),
        99: numpy.percentile(dists, 99),
    }
    if pct_lim not in percentiles[label]:
        percentiles[label][pct_lim] = lim


def damage_cid(cid, cell):
    return CellMeasure(report_id=cell.report_id,
                       lat=cell.lat,
                       lon=cell.lon,
                       mcc=cell.mcc,
                       mnc=cell.mnc,
                       lac=cell.lac,
                       cid=cid,
                       radio=cell.radio)

MLS_URL = "https://location.services.mozilla.com/v1"
MLS_GEO_URL = MLS_URL + "/geolocate?key=test"


def main():

    parser = argparse.ArgumentParser(
        description='Query ichnaea from true measurements, show divergence.')

    parser.add_argument("--geolocate",
                        help=("query geolocate API at nickname@url "
                              + "(default MLS@" + MLS_GEO_URL + ")"),
                        default=[],
                        action="append")

    parser.add_argument("--search",
                        help=("query search API at nickname@url "
                              + "(default none)"),
                        default=[],
                        action="append")

    parser.add_argument('--count', dest='count', type=int, default=100,
                        help='number of requests to make (default: 100)')

    parser.add_argument('--cell_measure', dest='cell_measure',
                        default='cell_measure.csv',
                        help=('source of cell measure ' +
                              '(default: cell_measure.csv)'))

    parser.add_argument('--wifi_measure', dest='wifi_measure',
                        default='wifi_measure.csv',
                        help=('source of wifi measure ' +
                              '(default: wifi_measure.csv)'))

    # Query and plot measuermenets with a cell, only where no wifi
    # was also present in the measurement
    parser.add_argument('--only-cell', dest='only_cell',
                        action='store_true', default=False)

    # Query and plot measuermenets with a wifi, only where no cell
    # was also present in the measurement
    parser.add_argument('--only-wifi', dest='only_wifi',
                        action='store_true', default=False)

    # Query and plot measuermenets with a cell, only where no wifi
    # was also present in the measurement, and the cell ID "damaged"
    # so that the service uses a LAC fallback.
    parser.add_argument('--only-lac', dest='only_lac',
                        action='store_true', default=False)

    # Query and plot measuermenets with a cell, omitting the wifi part
    # whether or not the measurement had a wifi present.
    parser.add_argument('--at-least-cell', dest='at_least_cell',
                        action='store_true', default=False)

    # Query and plot measurements with a wifi, omitting the cell part
    # whether or not the measurement had a cell present.
    parser.add_argument('--at-least-wifi', dest='at_least_wifi',
                        action='store_true', default=False)

    # Query and plot measurements with a cell value only and the
    # cell ID "damaged" so that the service uses a LAC fallback.
    parser.add_argument('--at-least-lac', dest='at_least_lac',
                        action='store_true', default=False)

    # Query and plot measurements where wifi and cell were both visible.
    parser.add_argument('--both', dest='both', action='store_true',
                        default=False)

    # Query and plot measurements where wifi and cell were both visible,
    # with cell ID "damaged" so that the service uses a LAC fallback.
    parser.add_argument('--both-lac', dest='both_lac', action='store_true',
                        default=False)

    # When damaging a cell measurement to provoke LAC-only response,
    # use this cellid.
    parser.add_argument('--lac-cellid', dest='lac_cellid', type=int,
                        default=101010101,
                        help='cellid to use for LAC-only queries')

    # Only use wifi measurements with >N APs visible, because the APIs
    # will reject queries with fewer for privacy sake. GLS and MLS both
    # have this constraint.
    parser.add_argument('--min-wifi', dest='min_wifi', type=int,
                        default=3,
                        help='minimum number of wifis per query, default 3')

    # By default, exclude radio type 3 (LTE) because it seems GLS doesn't
    # support that and we'd like our data sets to be comparable. Turn this
    # off by passing --exclude-radio=7 or something.
    parser.add_argument('--exclude-radio', dest='exclude_radio', type=int,
                        default=3,
                        help='exclude radios of this code #, default 3')

    # By default, only plot the lower 95% of samples; the outliers are
    # so far out that they tend to squish the overall shape of the plot.
    parser.add_argument('--plot-limit', dest='plot_limit', type=int,
                        default=95,
                        help='plot <= Nth percentile of data, default 95')

    args = parser.parse_args()

    cell_measures = defaultdict(list)
    wifi_measures = defaultdict(list)

    for cell in load_named_tuples_from_csv(CellMeasure, args.cell_measure):
        if cell.radio == args.exclude_radio:
            continue
        rid = cell.report_id
        cell_measures[rid].append(cell)

    for wifi in load_named_tuples_from_csv(WifiMeasure, args.wifi_measure):
        rid = wifi.report_id
        wifi_measures[rid].append(wifi)

    wifi_measures = dict([(k, v)
                          for (k, v)
                          in wifi_measures.items()
                          if len(v) > args.min_wifi])

    at_least_cell_report_ids = cell_measures.keys()
    at_least_wifi_report_ids = wifi_measures.keys()

    both_report_ids = list(set(at_least_cell_report_ids).intersection(
        set(at_least_wifi_report_ids)))

    only_cell_report_ids = list(set(at_least_cell_report_ids).difference(
        set(at_least_wifi_report_ids)))
    only_wifi_report_ids = list(set(at_least_wifi_report_ids).difference(
        set(at_least_cell_report_ids)))

    print("cell_measures: %d" % len(at_least_cell_report_ids))
    print("wifi_measures: %d" % len(at_least_wifi_report_ids))
    print("measures with both: %d" % len(both_report_ids))
    print("measures with only wifi: %d" % len(only_wifi_report_ids))
    print("measures with only cell: %d" % len(only_cell_report_ids))

    random.shuffle(at_least_cell_report_ids)
    random.shuffle(at_least_wifi_report_ids)
    random.shuffle(both_report_ids)
    random.shuffle(only_cell_report_ids)
    random.shuffle(only_wifi_report_ids)

    wn = min(len(only_wifi_report_ids), args.count)
    cn = min(len(only_cell_report_ids), args.count)
    bn = min(len(both_report_ids), args.count)

    variants = [
        ("both-wifi-and-cell", args.both,
         [TestQuery(lat=wifi_measures[rid][0].lat,
                    lon=wifi_measures[rid][0].lon,
                    cells=cell_measures[rid],
                    wifis=wifi_measures[rid])
          for rid in both_report_ids[:bn]]),

        ("both-wifi-and-lac", args.both_lac,
         [TestQuery(lat=wifi_measures[rid][0].lat,
                    lon=wifi_measures[rid][0].lon,
                    cells=[damage_cid(args.lac_cellid, cell)
                           for cell in cell_measures[rid]],
                    wifis=wifi_measures[rid])
          for rid in both_report_ids[:bn]]),

        ("at-least-wifi", args.at_least_wifi,
         [TestQuery(lat=wifi_measures[rid][0].lat,
                    lon=wifi_measures[rid][0].lon,
                    cells=[],
                    wifis=wifi_measures[rid])
          for rid in at_least_wifi_report_ids[:wn]]),

        ("at-least-cell", args.at_least_cell,
         [TestQuery(lat=cell_measures[rid][0].lat,
                    lon=cell_measures[rid][0].lon,
                    cells=cell_measures[rid],
                    wifis=[])
          for rid in at_least_cell_report_ids[:cn]]),

        ("at-least-lac", args.at_least_lac,
         [TestQuery(lat=cell_measures[rid][0].lat,
                    lon=cell_measures[rid][0].lon,
                    cells=[damage_cid(args.lac_cellid, cell)
                           for cell in cell_measures[rid]],
                    wifis=[])
          for rid in at_least_cell_report_ids[:cn]]),

        ("only-wifi", args.only_wifi,
         [TestQuery(lat=wifi_measures[rid][0].lat,
                    lon=wifi_measures[rid][0].lon,
                    cells=[],
                    wifis=wifi_measures[rid])
          for rid in only_wifi_report_ids[:wn]]),

        ("only-cell", args.only_cell,
         [TestQuery(lat=cell_measures[rid][0].lat,
                    lon=cell_measures[rid][0].lon,
                    cells=cell_measures[rid],
                    wifis=[])
          for rid in only_cell_report_ids[:cn]]),

        ("only-lac", args.only_lac,
         [TestQuery(lat=cell_measures[rid][0].lat,
                    lon=cell_measures[rid][0].lon,
                    cells=[damage_cid(args.lac_cellid, cell)
                           for cell in cell_measures[rid]],
                    wifis=[])
          for rid in only_cell_report_ids[:cn]])
    ]

    pylab.figure()

    percentiles = {}
    apis = []
    geolocate = args.geolocate
    if len(geolocate) == 0 and len(args.search) == 0:
        geolocate.append("MLS@" + MLS_GEO_URL)

    for geo in geolocate:
        (nick, url) = geo.split("@")
        apis.append((nick, url, geolocate_api, "geolocate"))

    for search in args.search:
        (nick, url) = search.split("@")
        apis.append((nick, url, search_api, "search"))

    for (nick, url, api, apiname) in apis:
        for (label, flag, tqs) in variants:
            if flag:
                print("\n\n" + label)
                plot_distance_and_accuracy(do_queries(url, api, tqs),
                                           percentiles, args.plot_limit,
                                           "%s %s %s" %
                                           (nick, apiname, label))

    pylab.xlabel("response distance in meters from GPS-measured location")
    pylab.ylabel("cumulative responses <= %d%% limit" % args.plot_limit)
    pylab.legend(loc='lower right')

    s = datetime.datetime.utcnow().isoformat() + ".png"
    pylab.savefig(s)
    print("\nplot saved to " + s)
    print("\npercentiles:")
    for (label, pct) in sorted(percentiles.items()):
        print("\n" + label)
        for (p, n) in sorted(pct.items()):
            print("\t%d: %.2fm" % (p, n))


if __name__ == "__main__":
    main()
