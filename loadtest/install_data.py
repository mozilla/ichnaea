import json
import os
from ichnaea.db import Database
from ichnaea.models import (
    Cell,
    Wifi,
)

from src.loadtest import (
    AP_FILE,
    TOWER_FILE,
    generate_data,
    JSONLocationDictDecoder,
)

SQLURI = os.environ.get('SQLURI')
SQLSOCKET = os.environ.get('SQLSOCKET')


def _make_db(create=True):
    return Database(SQLURI, socket=SQLSOCKET, create=create)


class DBFixture(object):

    def __init__(self):
        self.db_master = _make_db(False)

        master_conn = self.db_master.engine.connect()
        self.master_trans = master_conn.begin()
        self.db_master_session = self.db_master.session()

    def install_wifi_aps(self):
        self.db_master_session.execute(Wifi.__table__.delete())

        ap_data = json.load(open(AP_FILE),
                            object_hook=JSONLocationDictDecoder)

        session = self.db_master_session
        data = []
        for i, ((lat, lon), ap_set) in enumerate(ap_data.items()):
            for ap in ap_set:
                wifi = Wifi(key=ap['key'].replace(":", ""),
                            lat=lat * (10 ** 7),
                            lon=lon * (10 ** 7))
                data.append(wifi)
            session.add_all(data)
            session.commit()
            data = []

    def install_cell_towers(self):
        self.db_master_session.execute(Cell.__table__.delete())

        tower_data = json.load(open(TOWER_FILE),
                               object_hook=JSONLocationDictDecoder)

        session = self.db_master_session

        data = []
        for i, ((lat, lon), cell_data_set) in enumerate(tower_data.items()):
            for cell_data in cell_data_set:
                data.append(Cell(lat=lat * (10 ** 7),
                                 lon=lon * (10 ** 7),
                                 radio=cell_data['radio'],
                                 cid=cell_data['cid'],
                                 mcc=cell_data['mcc'],
                                 mnc=cell_data['mnc'],
                                 lac=cell_data['lac']))
            session.add_all(data)
            session.commit()
            data = []


if __name__ == '__main__':
    generate_data()
    db = DBFixture()
    db.install_wifi_aps()
    db.install_cell_towers()
