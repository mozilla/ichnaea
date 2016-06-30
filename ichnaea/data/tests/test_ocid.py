import csv
import os
import re
from contextlib import contextmanager
from datetime import datetime, timedelta

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
    CellShard,
    CellShardOCID,
    Radio,
    Stat,
    StatKey,
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


class TestExport(object):

    def test_local_export(self, celery, session):
        now = util.utcnow()
        today = now.date()
        long_ago = now - timedelta(days=367)
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
        # add one really old cell
        CellShardFactory(cid=220, created=long_ago, modified=long_ago,
                         last_seen=long_ago.date(), **cell_key)
        session.commit()

        with util.selfdestruct_tempdir() as temp_dir:
            path = os.path.join(temp_dir, 'export.csv.gz')
            write_stations_to_csv(session, path, today)

            with util.gzip_open(path, 'r') as gzip_wrapper:
                with gzip_wrapper as gzip_file:
                    reader = csv.DictReader(gzip_file, CELL_FIELDS)

                    header = six.next(reader)
                    assert 'area' in header.values()

                    exported_cells = set()
                    for exported_cell in reader:
                        exported_cell_filtered = [
                            (field, value) for (field, value)
                            in exported_cell.items()
                            if field in cell_fixture_fields]
                        exported_cell = tuple(sorted(exported_cell_filtered))
                        exported_cells.add(exported_cell)

                    assert cells == exported_cells

    def test_export_diff(self, celery, session):
        CellShardFactory.create_batch(10, radio=Radio.gsm)
        session.commit()
        pattern = re.compile(
            r'MLS-diff-cell-export-\d+-\d+-\d+T\d+0000\.csv\.gz')

        with mock_s3() as mock_key:
            cell_export_diff(_bucket='localhost.bucket')
            assert pattern.search(mock_key.key)
            method = mock_key.set_contents_from_filename
            assert pattern.search(method.call_args[0][0])

    def test_export_full(self, celery, session):
        now = util.utcnow()
        long_ago = now - timedelta(days=367)
        CellShardFactory.create_batch(10, radio=Radio.gsm)
        CellShardFactory(
            radio=Radio.gsm, created=long_ago,
            modified=long_ago, last_seen=long_ago.date())
        session.commit()
        pattern = re.compile(
            r'MLS-full-cell-export-\d+-\d+-\d+T000000\.csv\.gz')

        with mock_s3() as mock_key:
            cell_export_full(_bucket='localhost.bucket')
            assert pattern.search(mock_key.key)
            method = mock_key.set_contents_from_filename
            assert pattern.search(method.call_args[0][0])


class TestImport(object):

    @property
    def today(self):
        return util.utcnow().date()

    def check_stat(self, session, stat_key, value, time=None):
        if time is None:
            time = self.today
        stat = (session.query(Stat)
                       .filter(Stat.key == stat_key)
                       .filter(Stat.time == time)).first()
        assert stat.value == value

    @contextmanager
    def get_csv(self, cell, lo=1, hi=10, time=1408604686):
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

    def import_csv(self, celery, redis, session, cell,
                   lo=1, hi=10, time=1408604686, cell_type='ocid'):
        task = FakeTask(celery)
        with self.get_csv(cell, lo=lo, hi=hi, time=time) as path:
            with redis_pipeline(redis) as pipe:
                ImportLocal(task, cell_type=cell_type)(
                    pipe, session, filename=path)
        if cell_type == 'ocid':
            update_cellarea_ocid.delay().get()
        else:
            update_cellarea.delay().get()

    def test_import_local_cell(self, celery, redis, session):
        self.import_csv(
            celery, redis, session,
            CellShardFactory.build(radio=Radio.wcdma), cell_type='cell')
        cells = session.query(CellShard.shards()['wcdma']).all()
        assert len(cells) == 9

        areaids = set([cell.areaid for cell in cells])
        assert session.query(CellArea).count() == len(areaids)

        update_statcounter.delay().get()
        self.check_stat(session, StatKey.unique_cell, 9)

    def test_import_local_ocid(self, celery, redis, session):
        self.import_csv(
            celery, redis, session,
            CellShardFactory.build(radio=Radio.wcdma))
        cells = session.query(CellShardOCID.shards()['wcdma']).all()
        assert len(cells) == 9

        areaids = set([cell.areaid for cell in cells])
        assert session.query(CellAreaOCID).count() == len(areaids)

        update_statcounter.delay().get()
        self.check_stat(session, StatKey.unique_cell_ocid, 9)

    def test_import_local_delta(self, celery, redis, session):
        base_cell = CellShardFactory.build(radio=Radio.wcdma)
        old_time = 1407000000
        new_time = 1408000000
        old_date = datetime.utcfromtimestamp(old_time).replace(tzinfo=UTC)
        new_date = datetime.utcfromtimestamp(new_time).replace(tzinfo=UTC)

        self.import_csv(
            celery, redis, session,
            base_cell, time=old_time)
        cells = session.query(CellShardOCID.shards()['wcdma']).all()
        assert len(cells) == 9
        update_statcounter.delay().get()
        self.check_stat(session, StatKey.unique_cell_ocid, 9)

        areaids = set([cell.areaid for cell in cells])
        assert session.query(CellAreaOCID).count() == len(areaids)

        # update some entries
        self.import_csv(
            celery, redis, session,
            base_cell, lo=5, hi=13, time=new_time)
        session.commit()

        model = CellShardOCID.shards()['wcdma']
        cells = (session.query(model)
                        .order_by(model.modified).all())
        assert len(cells) == 12

        for i in range(0, 4):
            assert cells[i].modified == old_date

        for i in range(4, 12):
            assert cells[i].modified == new_date

        areaids = set([cell.areaid for cell in cells])
        assert session.query(CellAreaOCID).count() == len(areaids)

        update_statcounter.delay().get()
        self.check_stat(session, StatKey.unique_cell_ocid, 12)

    def test_import_external(self, celery, session):
        with self.get_csv(CellShardFactory.build(radio=Radio.wcdma)) as path:
            with open(path, 'rb') as gzip_file:
                with requests_mock.Mocker() as req_m:
                    req_m.register_uri('GET', re.compile('.*'), body=gzip_file)
                    cell_import_external.delay().get()

        update_cellarea_ocid.delay().get()

        model = CellShardOCID.shards()['wcdma']
        cells = (session.query(model)
                        .order_by(model.modified).all())
        assert len(cells) == 9

        areaids = set([cell.areaid for cell in cells])
        assert session.query(CellAreaOCID).count() == len(areaids)
