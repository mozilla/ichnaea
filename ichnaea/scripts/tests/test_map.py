import os
import os.path

from mock import MagicMock, patch

from ichnaea import ROOT
from ichnaea.models.content import (
    DATAMAP_SHARDS,
    DataMap,
)
from ichnaea.scripts import map as scripts_map
from ichnaea.scripts.map import (
    encode_file,
    export_file,
    main,
    merge_files,
    render_tiles,
)
from ichnaea.tests.base import (
    _make_db,
    CeleryTestCase,
)
from ichnaea import util

DATAMAPS_DIR = os.path.abspath(os.path.join(ROOT, os.pardir, 'datamaps'))


class TestMap(CeleryTestCase):

    def _check_quadtree(self, path):
        self.assertTrue(os.path.isdir(path))
        for name in ('1,0', 'meta'):
            self.assertTrue(os.path.isfile(os.path.join(path, name)))

    def test_files(self):
        today = util.utcnow().date()
        rows = [
            dict(time=today, lat=12.345, lon=12.345),
            dict(time=today, lat=0, lon=12.345),
            dict(time=today, lat=-10.000, lon=-11.000),
        ]
        for row in rows:
            lat, lon = DataMap.scale(row['lat'], row['lon'])
            data = DataMap.shard_model(lat, lon)(
                grid=(lat, lon), created=row['time'], modified=row['time'])
            self.session.add(data)
        self.session.flush()

        lines = []
        rows = 0
        with util.selfdestruct_tempdir() as temp_dir:
            quaddir = os.path.join(temp_dir, 'quadtrees')
            os.mkdir(quaddir)
            shapes = os.path.join(temp_dir, 'shapes')
            tiles = os.path.join(temp_dir, 'tiles')

            for shard_id, shard in DATAMAP_SHARDS.items():
                filename = 'map_%s.csv.gz' % shard_id
                filepath = os.path.join(temp_dir, filename)
                result = export_file(
                    None, filepath, shard.__tablename__,
                    _db_rw=_make_db(), _session=self.session)

                if not result:
                    self.assertFalse(os.path.isfile(filepath))
                    continue

                rows += result
                with util.gzip_open(filepath, 'r') as fd:
                    written = fd.read()
                lines.extend([line.split(',') for line in written.split()])

                encode_file(filename, temp_dir, quaddir, DATAMAPS_DIR)

                quadfolder = os.path.join(quaddir, 'map_' + shard_id)
                self.assertTrue(os.path.isdir(quadfolder))
                self._check_quadtree(quadfolder)

            merge_files(quaddir, shapes, DATAMAPS_DIR)
            self._check_quadtree(shapes)

            render_tiles(shapes, tiles, 1, 2, DATAMAPS_DIR)
            self.assertEqual(sorted(os.listdir(tiles)),
                             ['0', '1', '2'])
            self.assertEqual(sorted(os.listdir(os.path.join(tiles, '0', '0'))),
                             ['0.png', '0@2x.png'])

        self.assertEqual(rows, 36)
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
