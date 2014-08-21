import boto
import csv
import os
from contextlib import contextmanager
from mock import MagicMock, patch

from ichnaea.export.tasks import (
    export_modified_cells,
    write_stations_to_csv,
    make_cell_dict,
    selfdestruct_tempdir,
    CELL_COLUMNS,
    CELL_FIELDS,
    GzipFile
)
from ichnaea.models import Cell, cell_table, CELLID_LAC, RADIO_TYPE
from ichnaea.tests.base import CeleryTestCase


@contextmanager
def mock_s3():
    mock_conn = MagicMock()
    mock_key = MagicMock()
    with patch.object(boto, 'connect_s3', mock_conn):
        with patch('boto.s3.key.Key', lambda _: mock_key):
            yield mock_key


class TestExport(CeleryTestCase):

    def test_local_export(self):
        session = self.db_master_session
        k = dict(mcc=1, mnc=2, lac=4, lat=1.0, lon=2.0)
        for i in range(190, 200):
            session.add(Cell(radio=RADIO_TYPE['gsm'], cid=i, **k))
        session.commit()

        cond = cell_table.c.cid != CELLID_LAC
        header_row = dict([(cf, cf) for cf in CELL_FIELDS])

        with selfdestruct_tempdir() as d:
            path = os.path.join(d, 'export.csv.gz')
            write_stations_to_csv(session, cell_table, CELL_COLUMNS, cond,
                                  path, make_cell_dict, CELL_FIELDS)
            with GzipFile(path, "rb") as f:
                r = csv.DictReader(f, CELL_FIELDS)
                cid = 190
                for i, d in enumerate(r):
                    if i == 0:
                        self.assertEqual(d, header_row)
                        continue
                    t = dict(radio='GSM', cid=cid, **k)
                    t = dict([(n, str(v)) for (n, v) in t.items()])
                    self.assertDictContainsSubset(t, d)
                    cid += 1
                self.assertEqual(r.line_num, 11)
                self.assertEqual(cid, 200)

    def test_hourly_export(self):
        session = self.db_master_session
        gsm = RADIO_TYPE['gsm']
        k = dict(radio=gsm, mcc=1, mnc=2, lac=4, psc=-1, lat=1.0, lon=2.0)
        for i in range(190, 200):
            session.add(Cell(cid=i, **k))
        session.commit()

        with mock_s3() as mock_key:
            export_modified_cells(bucket="localhost.bucket")
            pat = r"MLS-diff-cell-export-\d+-\d+-\d+T\d+0000\.csv\.gz"
            self.assertRegexpMatches(mock_key.key, pat)
            method = mock_key.set_contents_from_filename
            self.assertRegexpMatches(method.call_args[0][0], pat)

    def test_daily_export(self):
        session = self.db_master_session
        gsm = RADIO_TYPE['gsm']
        k = dict(radio=gsm, mcc=1, mnc=2, lac=4, lat=1.0, lon=2.0)
        for i in range(190, 200):
            session.add(Cell(cid=i, **k))
        session.commit()

        with mock_s3() as mock_key:
            export_modified_cells(bucket="localhost.bucket", hourly=False)
            pat = r"MLS-full-cell-export-\d+-\d+-\d+T000000\.csv\.gz"
            self.assertRegexpMatches(mock_key.key, pat)
            method = mock_key.set_contents_from_filename
            self.assertRegexpMatches(method.call_args[0][0], pat)
