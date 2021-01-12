import os
import os.path
from multiprocessing import Pool
from unittest.mock import patch

import pytest

from ichnaea.models.content import DataMap
from ichnaea.scripts import datamap
from ichnaea.scripts.datamap import (
    csv_to_quadtree,
    export_to_csv,
    main,
    merge_quadtrees,
    render_tiles,
)
from ichnaea import util


@pytest.fixture
def temp_dir():
    with util.selfdestruct_tempdir() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_main_fixtures():
    with patch.object(
        datamap, "generate", return_value={}
    ) as mock_generate, patch.object(
        datamap, "check_bucket", return_value=(True, None)
    ) as mock_check_bucket:
        yield (mock_generate, mock_check_bucket)


class TestMap(object):
    def _check_quadtree(self, path):
        assert os.path.isdir(path)
        for name in ("1,0", "meta"):
            assert os.path.isfile(os.path.join(path, name))

    def test_files(self, session, temp_dir):
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
            session.add(data)
        session.flush()

        lines = []
        rows = 0

        quaddir = os.path.join(temp_dir, "quadtrees")
        os.mkdir(quaddir)
        shapes = os.path.join(temp_dir, "shapes")
        tiles = os.path.join(temp_dir, "tiles")

        for shard_id, shard in DataMap.shards().items():
            filename = f"map_{shard_id}.csv"
            filepath = os.path.join(temp_dir, filename)
            result = export_to_csv(filepath, shard.__tablename__, _session=session)

            if not result:
                assert not os.path.isfile(filepath)
                continue

            rows += result
            with open(filepath, "r") as fd:
                written = fd.read()
            lines.extend([line.split(",") for line in written.split()])

            csv_to_quadtree(filename, temp_dir, quaddir)

            quadfolder = os.path.join(quaddir, "map_" + shard_id)
            assert os.path.isdir(quadfolder)
            self._check_quadtree(quadfolder)

        merge_quadtrees(quaddir, shapes)
        self._check_quadtree(shapes)

        with Pool() as pool:
            render_tiles(pool, shapes, tiles, max_zoom=2)
        assert sorted(os.listdir(tiles)) == ["0", "1", "2"]
        assert sorted(os.listdir(os.path.join(tiles, "0", "0"))) == [
            "0.png",
            "0@2x.png",
        ]

        assert rows == 18
        assert len(lines) == 18
        lats = [round(float(line[0]), 2) for line in lines]
        longs = [round(float(line[1]), 2) for line in lines]
        assert set(lats) == set([-10.0, 0.0, 12.35])
        assert set(longs) == set([-11.0, 12.35])

    def test_main(self, raven, temp_dir, mock_main_fixtures):
        """main() calls generate with passed arguments"""
        mock_generate, mock_check_bucket = mock_main_fixtures
        argv = [
            "--create",
            "--upload",
            "--concurrency=1",
            f"--output={temp_dir}",
        ]
        main(argv, _raven_client=raven, _bucket_name="bucket")

        assert len(mock_generate.mock_calls) == 1
        args, kw = mock_generate.call_args
        assert args == (temp_dir, "bucket", raven)
        assert kw == {"concurrency": 1, "create": True, "upload": True}

        mock_check_bucket.assert_called_once_with("bucket")

    def test_main_create_only(self, raven, temp_dir, mock_main_fixtures):
        """main() can just generate tiles."""
        mock_generate, mock_check_bucket = mock_main_fixtures
        argv = ["--create", "--concurrency=1", f"--output={temp_dir}"]
        main(argv, _raven_client=raven, _bucket_name="bucket")

        assert len(mock_generate.mock_calls) == 1
        args, kw = mock_generate.call_args
        assert args == (temp_dir, "bucket", raven)
        assert kw == {"concurrency": 1, "create": True, "upload": False}

        assert not mock_check_bucket.mock_calls

    def test_main_upload_only(self, raven, temp_dir, mock_main_fixtures):
        """main() can upload if tiles subfolder exists."""
        mock_generate, mock_check_bucket = mock_main_fixtures
        tiles = os.path.join(temp_dir, "tiles")
        os.makedirs(tiles)

        argv = [
            "--upload",
            f"--output={temp_dir}",
            "--concurrency=1",
        ]
        result = main(argv, _raven_client=raven, _bucket_name="bucket")
        assert result == 0

        assert len(mock_generate.mock_calls) == 1
        args, kw = mock_generate.call_args
        assert args == (temp_dir, "bucket", raven)
        assert kw == {"concurrency": 1, "create": False, "upload": True}

        mock_check_bucket.assert_called_once_with("bucket")

    def test_main_tmp_dir(self, raven, mock_main_fixtures):
        """main() generates a temporary directory if --output omitted."""
        mock_generate, mock_check_bucket = mock_main_fixtures

        argv = ["--create", "--upload"]
        result = main(argv, _raven_client=raven, _bucket_name="bucket")
        assert result == 0

        assert len(mock_generate.mock_calls) == 1
        args, kw = mock_generate.call_args
        assert args[0]  # Some system-specific temporary folder
        assert not os.path.exists(args[0])
        assert args[1:] == ("bucket", raven)
        affinity = len(os.sched_getaffinity(0))
        assert kw == {"concurrency": affinity, "create": True, "upload": True}

        mock_check_bucket.assert_called_once_with("bucket")

    @pytest.mark.parametrize(
        "argv,exitcode",
        (([], 0), (["--create"], 1), (["--upload"], 1)),
        ids=("no args", "create no output", "upload no output"),
    )
    def test_main_early_exit(self, raven, mock_main_fixtures, argv, exitcode):
        """main() exits early for some argument combinations"""
        mock_generate, mock_check_bucket = mock_main_fixtures
        result = main(argv, _raven_client=raven, _bucket_name="bucket")
        assert result == exitcode

        assert not mock_generate.mock_calls
        assert not mock_check_bucket.mock_calls

    def test_main_upload_no_tiles_exits(self, raven, tmpdir, mock_main_fixtures):
        """main() exits early if upload folder has no tiles."""
        mock_generate, mock_check_bucket = mock_main_fixtures

        argv = ["--upload", f"--output={tmpdir}"]
        result = main(argv, _raven_client=raven, _bucket_name="bucket")
        assert result == 1

        assert not mock_generate.mock_calls
        assert not mock_check_bucket.mock_calls
