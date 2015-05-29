import csv
import os
import re
from contextlib import contextmanager
from datetime import datetime

import boto
from mock import MagicMock, patch
from pytz import UTC
import requests_mock

from ichnaea.constants import CELL_MIN_ACCURACY
from ichnaea.data.tasks import update_statcounter
from ichnaea.export.tasks import (
    export_modified_cells,
    import_ocid_cells,
    import_latest_ocid_cells,
    write_stations_to_csv,
    make_cell_export_dict,
    selfdestruct_tempdir,
    CELL_COLUMNS,
    CELL_FIELDS,
    CELL_HEADER_DICT,
    GzipFile
)
from ichnaea.models import (
    Cell,
    OCIDCell,
    OCIDCellArea,
    Radio,
    Stat,
    StatKey,
)
from ichnaea.tests.base import (
    CeleryTestCase,
    CeleryAppTestCase,
    FRANCE_MCC,
    VIVENDI_MNC,
    PARIS_LAT,
    PARIS_LON,
)
from ichnaea import util


@contextmanager
def mock_s3():
    mock_conn = MagicMock()
    mock_key = MagicMock()
    with patch.object(boto, 'connect_s3', mock_conn):
        with patch('boto.s3.key.Key', lambda _: mock_key):
            yield mock_key


class TestExport(CeleryTestCase):

    def test_local_export(self):
        session = self.session
        cell_fixture_fields = (
            'radio', 'cid', 'lat', 'lon', 'mnc', 'mcc', 'lac')
        cell_key = {'radio': Radio.gsm, 'mcc': 1, 'mnc': 2, 'lac': 4}
        cells = set()

        for cid in range(190, 200):
            cell = dict(cid=cid, lat=1.0, lon=2.0, **cell_key)
            session.add(Cell(**cell))

            cell['radio'] = 'GSM'
            cell_strings = [
                (field, str(value)) for (field, value) in cell.items()]
            cell_tuple = tuple(sorted(cell_strings))
            cells.add(cell_tuple)

        # add one incomplete / unprocessed cell
        session.add(Cell(cid=210, lat=None, lon=None, **cell_key))
        session.commit()

        with selfdestruct_tempdir() as temp_dir:
            path = os.path.join(temp_dir, 'export.csv.gz')
            cond = Cell.__table__.c.lat.isnot(None)
            write_stations_to_csv(
                session, Cell.__table__, CELL_COLUMNS, cond,
                path, make_cell_export_dict, CELL_FIELDS)

            with GzipFile(path, 'rb') as gzip_file:
                reader = csv.DictReader(gzip_file, CELL_FIELDS)

                header = reader.next()
                self.assertTrue('area' in header.values())
                self.assertEqual(header, CELL_HEADER_DICT)

                exported_cells = set()
                for exported_cell in reader:
                    exported_cell_filtered = [
                        (field, value) for (field, value)
                        in exported_cell.items()
                        if field in cell_fixture_fields]
                    exported_cell = tuple(sorted(exported_cell_filtered))
                    exported_cells.add(exported_cell)

                self.assertEqual(cells, exported_cells)

    def test_hourly_export(self):
        session = self.session
        k = {'radio': Radio.gsm, 'mcc': 1, 'mnc': 2, 'lac': 4,
             'psc': None, 'lat': 1.0, 'lon': 2.0}
        for i in range(190, 200):
            session.add(Cell(cid=i, **k))
        session.commit()

        with mock_s3() as mock_key:
            export_modified_cells(bucket='localhost.bucket')
            pat = r'MLS-diff-cell-export-\d+-\d+-\d+T\d+0000\.csv\.gz'
            self.assertRegexpMatches(mock_key.key, pat)
            method = mock_key.set_contents_from_filename
            self.assertRegexpMatches(method.call_args[0][0], pat)

    def test_daily_export(self):
        session = self.session
        k = {'radio': Radio.gsm, 'mcc': 1, 'mnc': 2, 'lac': 4,
             'lat': 1.0, 'lon': 2.0}
        for i in range(190, 200):
            session.add(Cell(cid=i, **k))
        session.commit()

        with mock_s3() as mock_key:
            export_modified_cells(bucket='localhost.bucket', hourly=False)
            pat = r'MLS-full-cell-export-\d+-\d+-\d+T000000\.csv\.gz'
            self.assertRegexpMatches(mock_key.key, pat)
            method = mock_key.set_contents_from_filename
            self.assertRegexpMatches(method.call_args[0][0], pat)


class TestImport(CeleryAppTestCase):
    KEY = {
        'mcc': FRANCE_MCC,
        'mnc': VIVENDI_MNC,
        'lac': 1234,
    }

    @contextmanager
    def get_test_csv(self, lo=1, hi=10, time=1408604686):
        line_template = ('GSM,{mcc},{mnc},{lac},{cid},,{lon},'
                         '{lat},1,1,1,{time},{time},')
        lines = [line_template.format(
            cid=i * 1010,
            lon=PARIS_LON + i * 0.002,
            lat=PARIS_LAT + i * 0.001,
            time=time,
            **self.KEY)
            for i in range(lo, hi)]
        txt = '\n'.join(lines)

        with selfdestruct_tempdir() as d:
            path = os.path.join(d, 'import.csv.gz')
            with GzipFile(path, 'wb') as f:
                f.write(txt)
            yield path

    def import_test_csv(self, lo=1, hi=10, time=1408604686, session=None):
        session = session or self.session
        with self.get_test_csv(lo=lo, hi=hi, time=time) as path:
            import_ocid_cells(path, session=session)

    def test_local_import(self):
        self.import_test_csv()
        cells = self.session.query(OCIDCell).all()
        self.assertEqual(len(cells), 9)

        lacs = set([
            (cell.radio, cell.mcc, cell.mnc, cell.lac) for cell in cells])
        self.assertEqual(
            self.session.query(OCIDCellArea).count(), len(lacs))

        update_statcounter.delay(ago=0).get()
        today = util.utcnow().date()
        stat_key = Stat.to_hashkey(key=StatKey.unique_ocid_cell, time=today)
        self.assertEqual(Stat.getkey(self.session, stat_key).value, 9)

    def test_local_import_with_query(self):
        self.session = self.db_ro_session
        self.import_test_csv(session=self.session)

        res = self.app.post_json(
            '/v1/search?key=test',
            {
                'radio': 'gsm',
                'cell': [
                    dict(cid=3030, **self.KEY),
                    dict(cid=4040, **self.KEY),
                ]
            },
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(
            res.json,
            {
                'status': 'ok',
                'lat': PARIS_LAT + 0.0035,
                'lon': PARIS_LON + 0.007,
                'accuracy': CELL_MIN_ACCURACY
            })

    def test_local_import_delta(self):
        old_time = 1407000000
        new_time = 1408000000
        old_date = datetime.fromtimestamp(old_time).replace(tzinfo=UTC)
        new_date = datetime.fromtimestamp(new_time).replace(tzinfo=UTC)
        today = util.utcnow().date()

        self.import_test_csv(time=old_time)
        cells = self.session.query(OCIDCell).all()
        self.assertEqual(len(cells), 9)
        update_statcounter.delay(ago=0).get()
        stat_key = Stat.to_hashkey(key=StatKey.unique_ocid_cell, time=today)
        self.assertEqual(Stat.getkey(self.session, stat_key).value, 9)

        lacs = set([
            (cell.radio, cell.mcc, cell.mnc, cell.lac) for cell in cells])
        self.assertEqual(
            self.session.query(OCIDCellArea).count(), len(lacs))

        # update some entries
        self.import_test_csv(lo=5, hi=13, time=new_time)

        cells = (self.session.query(OCIDCell)
                             .order_by(OCIDCell.modified).all())
        self.assertEqual(len(cells), 12)

        for i in range(0, 4):
            self.assertEqual(cells[i].modified, old_date)

        for i in range(4, 12):
            self.assertEqual(cells[i].modified, new_date)

        lacs = set([
            (cell.radio, cell.mcc, cell.mnc, cell.lac) for cell in cells])
        self.assertEqual(
            self.session.query(OCIDCellArea).count(), len(lacs))

        update_statcounter.delay(ago=0).get()
        stat_key = Stat.to_hashkey(key=StatKey.unique_ocid_cell, time=today)
        self.assertEqual(Stat.getkey(self.session, stat_key).value, 12)

    def test_local_import_latest_through_http(self):
        with self.get_test_csv() as path:
            with open(path, 'r') as f:
                with requests_mock.Mocker() as m:
                    m.register_uri('GET', re.compile('.*'), body=f)
                    import_latest_ocid_cells()

        cells = (self.session.query(OCIDCell)
                             .order_by(OCIDCell.modified).all())
        self.assertEqual(len(cells), 9)

        lacs = set([
            (cell.radio, cell.mcc, cell.mnc, cell.lac) for cell in cells])
        self.assertEqual(
            self.session.query(OCIDCellArea).count(), len(lacs))
