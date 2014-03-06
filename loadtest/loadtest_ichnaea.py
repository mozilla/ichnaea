import random


def random_cell():
    return {'cid': random.randint(0, 20000),
            'mnc': random.randint(0, 5),
            'lac': random.randint(0, 5),
            'mcc': random.randint(0, 5),
            'radio': random.randint(0, 3),
            'lat': random.randint(-900000000, 900000000),
            'lon': random.randint(-900000000, 900000000),
            }

"""
Generate 10,000 lat/long pairs
For each pair, generate 1-10 cell towers
"""

MAX_LATLONG_PAIRS = 10000
MAX_TOWERS = 10

def random_ap():
    key = binascii.b2a_hex(os.urandom(15))[:12]
    key = ':'.join(key[i:i+2] for i in range(0, len(key), 2))
    return {"key": key,
            "channel": random.randint(0, 12),
            "frequency": random.randint(0, 5000),
            "channel": random.randint(1, 12),
            "signal": random.randint(0, -50)}

def generate_wifi_aps():
    ap_data = {}
    for i in range(MAX_LATLONG_PAIRS):
        lat = random.randint(-900000000, 900000000)
        lon = random.randint(-900000000, 900000000)
        ap_data[(lat, lon)] = []

        for x in range(random.randint(1, 20)):
            rcell = random_cell()
            ap_data[(lat, lon)].append({"radio": rcell['radio'],
                                           "mcc": rcell['mcc'],
                                           "mnc": rcell['mnc'],
                                           "lac": rcell['lac'],
                                           "cid": rcell['cid']})
    return ap_data


def generate_towers():
    tower_data = {}
    for i in range(MAX_LATLONG_PAIRS):
        lat = random.randint(-900000000, 900000000)
        lon = random.randint(-900000000, 900000000)
        tower_data[(lat, lon)] = []

        for x in range(random.randint(1, 20)):
            rcell = random_cell()

            tower_data[(lat, lon)].append({"radio": rcell['radio'],
                                           "mcc": rcell['mcc'],
                                           "mnc": rcell['mnc'],
                                           "lac": rcell['lac'],
                                           "cid": rcell['cid']})
    return tower_data


def main():
    tower_data = generate_towers()
    ap_data = generate_wifi_aps()

    cell_records = 0
    ap_records = 0

    for v in tower_data.values():
        cell_records += len(v)

    for v in ap_data.values():
        ap_records += len(v)

    print "Got %d towers" % cell_records
    print "Got %d AP" % ap_records


if __name__ == '__main__':
    main()
