import os

from mock import MagicMock, patch

from ichnaea.models.content import MapStat
from ichnaea.scripts import map as scripts_map
from ichnaea.scripts.map import (
    export_file,
    main,
)
from ichnaea.tests.base import (
    _make_db,
    CeleryTestCase,
)
from ichnaea import util


class TestMap(CeleryTestCase):

    def test_export_file(self):
        today = util.utcnow().date()
        data = [
            MapStat(time=today, lat=12345, lon=12345),
            MapStat(time=today, lat=0, lon=12345),
            MapStat(time=today, lat=None, lon=None),
            MapStat(time=today, lat=-10000, lon=-11000),
        ]
        self.session.add_all(data)
        self.session.flush()

        with util.selfdestruct_tempdir() as temp_dir:
            filename = os.path.join(temp_dir, 'map.csv.gz')

            result = export_file(
                None, filename, -85051, 85052, -180000, 180001,
                _db_rw=_make_db(), _session=self.session)
            self.assertEqual(result, 36)

            with util.gzip_open(filename, 'r') as fd:
                written = fd.read()
            lines = [line.split(',') for line in written.split()]
            self.assertEqual(len(lines), 36)
            self.assertEqual(set([round(float(l[0]), 2) for l in lines]),
                             set([-10.0, 0.0, 12.35]))
            self.assertEqual(set([round(float(l[1]), 2) for l in lines]),
                             set([-11.0, 12.35]))

    def test_main(self):
        with util.selfdestruct_tempdir() as temp_dir:
            mock_generate = MagicMock()
            with patch.object(scripts_map, 'generate', mock_generate):
                argv = [
                    'bin/location_map',
                    '--create',
                    '--upload',
                    '--concurrency=1',
                    '--datamaps=%s/datamaps' % temp_dir,
                    '--output=%s' % temp_dir,
                ]
                main(argv,
                     _raven_client=self.raven_client,
                     _stats_client=self.stats_client)

                self.assertEqual(len(mock_generate.mock_calls), 1)
                args, kw = mock_generate.call_args

                self.assertEqual(kw['concurrency'], 1)
                self.assertEqual(kw['datamaps'], temp_dir + '/datamaps')
                self.assertEqual(kw['output'], temp_dir)
                self.assertEqual(kw['upload'], True)
