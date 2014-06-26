import requests
import json
import time
import argparse


HOST = 'localhost'


def submit_test():
    wifi_data = [{"key": "0012AB12AB12"}, {"key": "00:34:cd:34:cd:34"}]
    payload = json.dumps({"items": [{"lat": 12.3456781,
                                     "lon": 23.4567892,
                                     "accuracy": 17,
                                     "wifi": wifi_data}]})

    expected_status = 204

    while True:
        try:
            r = requests.post('http://127.0.0.1:7001/v1/submit',
                              data=payload)
            print r.status_code, time.time()
            assert r.status_code == expected_status
        except:
            pass


def search_test():
    key = dict(mcc=1, mnc=2, lac=3)
    payload = json.dumps({"radio": "gsm", "cell": [
        dict(radio="umts", cid=4, **key),
        dict(radio="umts", cid=5, **key),
    ], "wifi": [
        {"key": "abcd"},
        {"key": "cdef"},
    ]})

    while True:
        try:
            r = requests.post('http://127.0.0.1:7001/v1/search?key=test',
                              data=payload)

            print r.status_code, r.content, time.time()
        except:
            pass

parser = argparse.ArgumentParser(description='Test the ichnaea server')
parser.add_argument('--search',
                    action='store_true',
                    help='Run a search test')
parser.add_argument('--submit',
                    action='store_true',
                    help='Run a submit test')

args = parser.parse_args()
if args.search:
    search_test()
elif args.submit:
    submit_test()
else:
    parser.print_help()
