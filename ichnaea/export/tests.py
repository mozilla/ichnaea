import boto
import csv
import os
from datetime import datetime
from pytz import UTC
from contextlib import contextmanager
from mock import MagicMock, patch

from ichnaea.export.tasks import (
    export_modified_cells,
    import_ocid_cells,
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
    cell_table,
    CELLID_LAC,
    RADIO_TYPE,
    CELL_MIN_ACCURACY
)
from ichnaea.tests.base import (
    CeleryTestCase,
    CeleryAppTestCase,
    FRANCE_MCC,
    VIVENDI_MNC,
    PARIS_LAT,
    PARIS_LON,
)


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

        with selfdestruct_tempdir() as d:
            path = os.path.join(d, 'export.csv.gz')
            write_stations_to_csv(session, cell_table, CELL_COLUMNS,
                                  cell_table.c.cid != CELLID_LAC,
                                  path, make_cell_export_dict, CELL_FIELDS)
            with GzipFile(path, "rb") as f:
                r = csv.DictReader(f, CELL_FIELDS)

                header = r.next()
                self.assertTrue('area' in header.values())
                self.assertEqual(header, CELL_HEADER_DICT)

                cid = 190
                for d in r:
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


class TestImport(CeleryAppTestCase):

    def test_local_import(self):
        txt = """\
GSM,302,2,4,190,,2.0,1.0,0,0,1,1408604686,1408604686,
GSM,302,2,4,191,,2.0,1.0,0,0,1,1408604686,1408604686,
GSM,302,2,4,192,,2.0,1.0,0,0,1,1408604686,1408604686,
GSM,302,2,4,193,,2.0,1.0,0,0,1,1408604686,1408604686,
GSM,302,2,4,194,,2.0,1.0,0,0,1,1408604686,1408604686,
GSM,302,2,4,195,,2.0,1.0,0,0,1,1408604686,1408604686,
GSM,302,2,4,196,,2.0,1.0,0,0,1,1408604686,1408604686,
GSM,302,2,4,197,,2.0,1.0,0,0,1,1408604686,1408604686,
GSM,302,2,4,198,,2.0,1.0,0,0,1,1408604686,1408604686,
GSM,302,2,4,199,,2.0,1.0,0,0,1,1408604686,1408604686,
"""
        with selfdestruct_tempdir() as d:
            path = os.path.join(d, "import.csv.gz")
            with GzipFile(path, 'wb') as f:
                f.write(txt)
            import_ocid_cells(path)

        sess = self.db_master_session
        cells = sess.query(OCIDCell).all()
        self.assertEqual(len(cells), 10)

    def do_import_lines(self, lo, hi, key, time=1408604686):

        lines = [
            str.format("GSM,{mcc},{mnc},{lac},{cid}," +
                       ",{lon},{lat},1,1,1,{time},{time},",
                       cid=i * 1010,
                       lon=PARIS_LON + i * 0.002,
                       lat=PARIS_LAT + i * 0.001,
                       time=time, **key)
            for i in range(lo, hi)]
        txt = "\n".join(lines)

        with selfdestruct_tempdir() as d:
            path = os.path.join(d, "import.csv.gz")
            with GzipFile(path, 'wb') as f:
                f.write(txt)
            import_ocid_cells(path, sess=self.db_slave_session)

    def test_local_import_with_query(self):

        key = dict(mcc=FRANCE_MCC,
                   mnc=VIVENDI_MNC,
                   lac=1234)

        self.do_import_lines(1, 10, key)

        res = self.app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(cid=3030, **key),
                dict(cid=4040, **key),
            ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": PARIS_LAT + 0.0035,
                                    "lon": PARIS_LON + 0.007,
                                    "accuracy": CELL_MIN_ACCURACY})

    def test_local_import_delta(self):

        key = dict(mcc=FRANCE_MCC,
                   mnc=VIVENDI_MNC,
                   lac=1234)

        sess = self.db_slave_session
        self.do_import_lines(1, 10, key, time=1407000000)
        cells = sess.query(OCIDCell).all()
        sess.commit()
        self.assertEqual(len(cells), 9)

        # update some entries
        self.do_import_lines(5, 10, key, time=1408000000)
        cells = sess.query(OCIDCell).order_by(OCIDCell.modified).all()
        self.assertEqual(len(cells), 9)

        old = datetime.fromtimestamp(1407000000).replace(tzinfo=UTC)
        new = datetime.fromtimestamp(1408000000).replace(tzinfo=UTC)

        for i in range(0, 4):
            self.assertEqual(cells[i].modified, old)

        for i in range(4, 9):
            self.assertEqual(cells[i].modified, new)
