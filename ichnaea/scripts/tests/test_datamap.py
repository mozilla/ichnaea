import os
import os.path
from unittest.mock import MagicMock, patch

from ichnaea.models.content import DataMap
from ichnaea.scripts import datamap
from ichnaea.scripts.datamap import (
    encode_file,
    export_file,
    main,
    merge_files,
    render_tiles,
)
from ichnaea import util


class TestMap(object):
    def _check_quadtree(self, path):
        assert os.path.isdir(path)
        for name in ("1,0", "meta"):
            assert os.path.isfile(os.path.join(path, name))

    def test_files(self, sync_session):
        today = util.utcnow().date()
        rows = [
            dict(time=today, lat=12.345, lon=12.345),
            dict(time=today, lat=0, lon=12.345),
            dict(time=today, lat=-10.000, lon=-11.000),
        ]
        for row in rows:
            lat, lon = DataMap.scale(row["lat"], row["lon"])
            data = DataMap.shard_model(lat, lon)(
                grid=(lat, lon), created=row["time"], modified=row["time"]
            )
            sync_session.add(data)
        sync_session.flush()

        lines = []
        rows = 0

        with util.selfdestruct_tempdir() as temp_dir:
            quaddir = os.path.join(temp_dir, "quadtrees")
            os.mkdir(quaddir)
            shapes = os.path.join(temp_dir, "shapes")
            tiles = os.path.join(temp_dir, "tiles")

            for shard_id, shard in DataMap.shards().items():
                filename = "map_%s.csv.gz" % shard_id
                filepath = os.path.join(temp_dir, filename)
                result = export_file(
                    filepath, shard.__tablename__, _session=sync_session
                )

                if not result:
                    assert not os.path.isfile(filepath)
                    continue

                rows += result
                with util.gzip_open(filepath, "r") as fd:
                    written = fd.read()
                lines.extend([line.split(",") for line in written.split()])

                encode_file(filename, temp_dir, quaddir)

                quadfolder = os.path.join(quaddir, "map_" + shard_id)
                assert os.path.isdir(quadfolder)
                self._check_quadtree(quadfolder)

            merge_files(quaddir, shapes)
            self._check_quadtree(shapes)

            render_tiles(shapes, tiles, 1, 2)
            assert sorted(os.listdir(tiles)) == ["0", "1", "2"]
            assert sorted(os.listdir(os.path.join(tiles, "0", "0"))) == [
                "0.png",
                "0@2x.png",
            ]

        assert rows == 18
        assert len(lines) == 18
        assert set([round(float(l[0]), 2) for l in lines]) == set([-10.0, 0.0, 12.35])
        assert set([round(float(l[1]), 2) for l in lines]) == set([-11.0, 12.35])

    def test_main(self, raven):
        with util.selfdestruct_tempdir() as temp_dir:
            mock_generate = MagicMock()
            with patch.object(datamap, "generate", mock_generate):
                argv = [
                    "bin/location_map",
                    "--create",
                    "--upload",
                    "--concurrency=1",
                    "--output=%s" % temp_dir,
                ]
                main(argv, _raven_client=raven, _bucketname="bucket")

                assert len(mock_generate.mock_calls) == 1
                args, kw = mock_generate.call_args

                assert kw["concurrency"] == 1
                assert kw["output"] == temp_dir
                assert kw["upload"] is True
