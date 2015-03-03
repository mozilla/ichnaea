from contextlib import contextmanager
import os
from tempfile import mkstemp

from mock import MagicMock, patch

from ichnaea.models.content import MapStat
from ichnaea.scripts import map as scripts_map
from ichnaea.scripts.map import (
    export_to_csv,
    generate,
    main,
    tempdir,
)
from ichnaea.tests.base import CeleryTestCase


@contextmanager
def mock_system_call():
    mock_system = MagicMock()
    with patch.object(scripts_map, 'system_call', mock_system):
        yield mock_system


class TestMap(CeleryTestCase):

    def test_export_to_csv(self):
        session = self.session
        data = [
            MapStat(lat=12345, lon=12345),
            MapStat(lat=0, lon=12345),
            MapStat(lat=0, lon=0),
            MapStat(lat=-10000, lon=-11000),
        ]
        session.add_all(data)
        session.flush()

        fd, filename = mkstemp()
        try:
            result = export_to_csv(session, filename, multiplier=3)
            self.assertEqual(result, 9)
            written = os.read(fd, 10240)
            lines = [line.split(',') for line in written.split()]
            self.assertEqual(len(lines), 9)
            self.assertEqual(set([round(float(l[0]), 2) for l in lines]),
                             set([-10.0, 0.0, 12.35]))
            self.assertEqual(set([round(float(l[1]), 2) for l in lines]),
                             set([-11.0, 12.35]))
        finally:
            os.remove(filename)

    def test_generate(self):
        with mock_system_call() as mock_system:
            generate(self.db_rw, 's3_bucket',
                     self.heka_client, self.stats_client,
                     upload=False, concurrency=1, datamaps='')
            mock_calls = mock_system.mock_calls
            self.assertEqual(len(mock_calls), 3)
            self.assertTrue(mock_calls[0][1][0].startswith('encode'))
            self.assertTrue(mock_calls[1][1][0].startswith('enumerate'))
            self.assertTrue(mock_calls[2][1][0].startswith('enumerate'))
        self.check_stats(
            timer=['datamaps.export_to_csv',
                   'datamaps.csv_rows',
                   'datamaps.encode',
                   'datamaps.render'])

    def test_generate_explicit_output(self):
        with tempdir() as temp_dir:
            with mock_system_call() as mock_system:
                generate(self.db_rw, 's3_bucket',
                         self.heka_client, self.stats_client,
                         upload=False, concurrency=1,
                         datamaps='', output=temp_dir)
                mock_calls = mock_system.mock_calls
                self.assertEqual(len(mock_calls), 3)

    def test_main(self):
        with tempdir() as temp_dir:
            with mock_system_call() as mock_system:
                argv = [
                    'bin/location_map',
                    '--create',
                    '--concurrency=1',
                    '--datamaps=%s' % temp_dir,
                    '--output=%s' % temp_dir,
                ]
                main(argv,
                     _db_rw=self.db_rw,
                     _heka_client=self.heka_client,
                     _stats_client=self.stats_client)
                mock_calls = mock_system.mock_calls
                self.assertEqual(len(mock_calls), 3)
