import csv
import os
import re
from contextlib import contextmanager
from datetime import datetime

import boto
from mock import MagicMock, patch
from pytz import UTC
import requests_mock
import six

from ichnaea.cache import redis_pipeline
from ichnaea.data.ocid import (
    ImportLocal,
    write_stations_to_csv,
)
from ichnaea.data.tasks import (
    cell_export_full,
    cell_export_diff,
    cell_import_external,
    update_cellarea,
    update_cellarea_ocid,
    update_statcounter,
)
from ichnaea.models import (
    CellArea,
    CellAreaOCID,
    CellOCID,
    CellShard,
    Radio,
    Stat,
    StatKey,
)
from ichnaea.tests.base import (
    CeleryTestCase,
    CeleryAppTestCase,
)
from ichnaea.tests.factories import CellShardFactory
from ichnaea import util

CELL_FIELDS = [
    'radio', 'mcc', 'mnc', 'lac', 'cid', 'psc',
    'lon', 'lat', 'range', 'samples', 'changeable',
    'created', 'updated', 'averageSignal']


@contextmanager
def mock_s3():
    mock_conn = MagicMock()
    mock_key = MagicMock()
    with patch.object(boto, 'connect_s3', mock_conn):
        with patch('boto.s3.key.Key', lambda _: mock_key):
            yield mock_key


class FakeTask(object):

    def __init__(self, app):
        self.app = app


class TestExport(CeleryTestCase):

    def test_local_export(self):
        cell_fixture_fields = (
            'radio', 'cid', 'lat', 'lon', 'mnc', 'mcc', 'lac')
        base_cell = CellShardFactory.build(radio=Radio.wcdma)
        cell_key = {'radio': Radio.wcdma, 'mcc': base_cell.mcc,
                    'mnc': base_cell.mnc, 'lac': base_cell.lac}
        cells = set()

        for cid in range(190, 200):
            cell = dict(cid=cid, lat=base_cell.lat,
                        lon=base_cell.lon, **cell_key)
            CellShardFactory(**cell)
            cell['lat'] = '%.7f' % cell['lat']
            cell['lon'] = '%.7f' % cell['lon']

            cell['radio'] = 'UMTS'
            cell_strings = [
                (field, str(value)) for (field, value) in cell.items()]
            cell_tuple = tuple(sorted(cell_strings))
            cells.add(cell_tuple)

        # add one incomplete / unprocessed cell
        CellShardFactory(cid=210, lat=None, lon=None, **cell_key)
        self.session.commit()

        with util.selfdestruct_tempdir() as temp_dir:
            path = os.path.join(temp_dir, 'export.csv.gz')
            write_stations_to_csv(self.session, path)

            with util.gzip_open(path, 'r') as gzip_wrapper:
                with gzip_wrapper as gzip_file:
                    reader = csv.DictReader(gzip_file, CELL_FIELDS)

                    header = six.next(reader)
                    self.assertTrue('area' in header.values())

                    exported_cells = set()
                    for exported_cell in reader:
                        exported_cell_filtered = [
                            (field, value) for (field, value)
                            in exported_cell.items()
                            if field in cell_fixture_fields]
                        exported_cell = tuple(sorted(exported_cell_filtered))
                        exported_cells.add(exported_cell)

                    self.assertEqual(cells, exported_cells)

    def test_export_diff(self):
        CellShardFactory.create_batch(10, radio=Radio.gsm)
        self.session.commit()

        with mock_s3() as mock_key:
            cell_export_diff(_bucket='localhost.bucket')
            pat = r'MLS-diff-cell-export-\d+-\d+-\d+T\d+0000\.csv\.gz'
            self.assertRegex(mock_key.key, pat)
            method = mock_key.set_contents_from_filename
            self.assertRegex(method.call_args[0][0], pat)

    def test_export_full(self):
        CellShardFactory.create_batch(10, radio=Radio.gsm)
        self.session.commit()

        with mock_s3() as mock_key:
            cell_export_full(_bucket='localhost.bucket')
            pat = r'MLS-full-cell-export-\d+-\d+-\d+T000000\.csv\.gz'
            self.assertRegex(mock_key.key, pat)
            method = mock_key.set_contents_from_filename
            self.assertRegex(method.call_args[0][0], pat)


class TestImport(CeleryAppTestCase):

    def setUp(self):
        super(TestImport, self).setUp()
        self.cell = CellShardFactory.build(radio=Radio.wcdma)
        self.today = util.utcnow().date()

    def check_stat(self, stat_key, value, time=None):
        if time is None:
            time = self.today
        stat = (self.session.query(Stat)
                            .filter(Stat.key == stat_key)
                            .filter(Stat.time == time)).first()
        self.assertEqual(stat.value, value)

    @contextmanager
    def get_csv(self, lo=1, hi=10, time=1408604686):
        cell = self.cell
        line_template = ('UMTS,{mcc},{mnc},{lac},{cid},{psc},{lon:.7f},'
                         '{lat:.7f},1,1,1,{time},{time},')
        lines = [line_template.format(
            mcc=cell.mcc, mnc=cell.mnc, lac=cell.lac, cid=i * 1010, psc='',
            lon=cell.lon + i * 0.002,
            lat=cell.lat + i * 0.001,
            time=time)
            for i in range(lo, hi)]
        # add bad lines
        lines.append(line_template.format(
            mcc=cell.mcc, mnc=cell.mnc,
            lac='', cid='', psc=12,
            lon=cell.lon, lat=cell.lat, time=time,
        ))
        lines.append(line_template.format(
            mcc=cell.mcc, mnc=cell.mnc,
            lac='', cid='', psc='',
            lon=cell.lon, lat=cell.lat, time=time,
        ))
        txt = '\n'.join(lines)

        with util.selfdestruct_tempdir() as temp_dir:
            path = os.path.join(temp_dir, 'import.csv.gz')
            with util.gzip_open(path, 'w') as gzip_wrapper:
                with gzip_wrapper as gzip_file:
                    gzip_file.write(txt)
            yield path

    def import_csv(self, lo=1, hi=10, time=1408604686, cell_type='ocid'):
        task = FakeTask(self.celery_app)
        with self.get_csv(lo=lo, hi=hi, time=time) as path:
            with redis_pipeline(self.redis_client) as pipe:
                ImportLocal(task, self.session, pipe,
                            cell_type=cell_type)(filename=path)
        if cell_type == 'ocid':
            update_cellarea_ocid.delay().get()
        else:
            update_cellarea.delay().get()

    def test_import_local_cell(self):
        self.import_csv(cell_type='cell')
        cells = self.session.query(CellShard.shards()['wcdma']).all()
        self.assertEqual(len(cells), 9)

        areaids = set([cell.areaid for cell in cells])
        self.assertEqual(
            self.session.query(CellArea).count(), len(areaids))

        update_statcounter.delay(ago=0).get()
        self.check_stat(StatKey.unique_cell, 9)

    def test_import_local_ocid(self):
        self.import_csv()
        cells = self.session.query(CellOCID).all()
        self.assertEqual(len(cells), 9)

        areaids = set([cell.areaid for cell in cells])
        self.assertEqual(
            self.session.query(CellAreaOCID).count(), len(areaids))

        update_statcounter.delay(ago=0).get()
        self.check_stat(StatKey.unique_cell_ocid, 9)

    def test_import_local_delta(self):
        old_time = 1407000000
        new_time = 1408000000
        old_date = datetime.utcfromtimestamp(old_time).replace(tzinfo=UTC)
        new_date = datetime.utcfromtimestamp(new_time).replace(tzinfo=UTC)

        self.import_csv(time=old_time)
        cells = self.session.query(CellOCID).all()
        self.assertEqual(len(cells), 9)
        update_statcounter.delay(ago=0).get()
        self.check_stat(StatKey.unique_cell_ocid, 9)

        areaids = set([cell.areaid for cell in cells])
        self.assertEqual(
            self.session.query(CellAreaOCID).count(), len(areaids))

        # update some entries
        self.import_csv(lo=5, hi=13, time=new_time)
        self.session.commit()

        cells = (self.session.query(CellOCID)
                             .order_by(CellOCID.modified).all())
        self.assertEqual(len(cells), 12)

        for i in range(0, 4):
            self.assertEqual(cells[i].modified, old_date)

        for i in range(4, 12):
            self.assertEqual(cells[i].modified, new_date)

        areaids = set([cell.areaid for cell in cells])
        self.assertEqual(
            self.session.query(CellAreaOCID).count(), len(areaids))

        update_statcounter.delay(ago=0).get()
        self.check_stat(StatKey.unique_cell_ocid, 12)

    def test_import_external(self):
        with self.get_csv() as path:
            with open(path, 'rb') as gzip_file:
                with requests_mock.Mocker() as req_m:
                    req_m.register_uri('GET', re.compile('.*'), body=gzip_file)
                    cell_import_external.delay().get()

        update_cellarea_ocid.delay().get()
        cells = (self.session.query(CellOCID)
                             .order_by(CellOCID.modified).all())
        self.assertEqual(len(cells), 9)

        areaids = set([cell.areaid for cell in cells])
        self.assertEqual(
            self.session.query(CellAreaOCID).count(), len(areaids))
