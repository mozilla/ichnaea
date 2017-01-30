import os.path

from ichnaea.conftest import GB_LAT, GB_LON
from ichnaea.scripts import dump
from ichnaea.tests.factories import (
    BlueShardFactory,
    CellShardFactory,
    CellShardOCIDFactory,
    WifiShardFactory,
)
from ichnaea import util


def _dump_nothing(datatype, session, filename,
                  lat=None, lon=None, radius=None):
    return 0


class TestDump(object):

    def test_compiles(self):
        assert hasattr(dump, 'console_entry')

    def test_main(self, db):
        assert dump.main(
            ['script', '--datatype=blue', '--filename=/tmp/foo.tar.gz',
             '--lat=51.0', '--lon=0.1', '--radius=25000'],
            _db=db, _dump_file=_dump_nothing) == 0

    def test_where(self):
        assert dump.where_area(None, None, None) is None
        assert dump.where_area(GB_LAT, None, None) is None
        assert dump.where_area(GB_LAT, GB_LON, None) is None
        assert dump.where_area(GB_LAT, GB_LON, 25000) == (
            '`lat` <= 51.7247 and `lat` >= 51.27529 and '
            '`lon` <= 0.26002 and `lon` >= -0.46002')

    def _export(self, session, datatype, expected_keys, restrict=False):
        with util.selfdestruct_tempdir() as temp_dir:
            path = os.path.join(temp_dir, datatype + '.tar.gz')
            if restrict:
                dump.dump_file(datatype, session, path,
                               lat=GB_LAT, lon=GB_LON, radius=25000)
            else:
                dump.dump_file(datatype, session, path)

            assert os.path.isfile(path)
            with util.gzip_open(path, 'r') as fd:
                lines = fd.readlines()
                assert len(lines) == len(expected_keys) + 1
                for key in expected_keys:
                    assert [True for line in lines if key in line] == [True]

    def _cell_keys(self, cells):
        keys = []
        for cell in cells:
            keys.append(','.join(
                [cell.radio.name.upper()] + [str(c) for c in cell.cellid[1:]]))
        return keys

    def _mac_keys(self, networks):
        return [network.mac for network in networks]

    def test_blue(self, session):
        # Add one network outside the desired area.
        BlueShardFactory(lat=46.5743, lon=6.3532, region='FR')
        blues = BlueShardFactory.create_batch(1)
        session.flush()
        self._export(session, 'blue', self._mac_keys(blues), restrict=True)

    def test_cell(self, session):
        cells = CellShardFactory.create_batch(2)
        # Add one far away network, with no area restriction.
        cells.append(CellShardFactory(lat=46.5743, lon=6.3532, region='FR'))
        session.flush()
        self._export(session, 'cell', self._cell_keys(cells))

    def test_cell_ocid(self, session):
        cells = CellShardOCIDFactory.create_batch(3)
        session.flush()
        self._export(session, 'ocid', self._cell_keys(cells))

    def test_wifi(self, session):
        wifis = WifiShardFactory.create_batch(5)
        session.flush()
        self._export(session, 'wifi', self._mac_keys(wifis))
