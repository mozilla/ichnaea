import os
import os.path
import re
from multiprocessing import Pool
from unittest.mock import patch, MagicMock, Mock

import pytest

from ichnaea.models.content import DataMap, encode_datamap_grid
from ichnaea.scripts import datamap
from ichnaea.scripts.datamap import (
    csv_to_quadtree,
    csv_to_quadtrees,
    export_to_csv,
    generate,
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


@pytest.fixture
def mock_db_worker_session():
    """
    Mock the db_worker_session used in export_to_csv()

    Other tests use the database test fixtures, but they can't be used in
    export_to_csv when called from export_to_csvs, because the test
    fixtures can't be pickled. This complicated mock works around that
    limitation by patching db_worker_session directly.
    """

    class FakeQueryItem:
        """A fake query row with .grid and .num"""

        def __init__(self, lat, lon):
            self.grid = encode_datamap_grid(*DataMap.scale(lat, lon))
            self.num = 0

    # Test data, by database table
    test_data = {
        "datamap_ne": [],
        "datamap_nw": [],
        "datamap_se": [
            [FakeQueryItem(lat=12.345, lon=12.345)],
            [FakeQueryItem(lat=0, lon=12.345)],
        ],
        "datamap_sw": [[FakeQueryItem(lat=-10.000, lon=-11.000)]],
    }

    # The expected SQL statement, with binding placeholders
    re_stmt = re.compile(
        r"SELECT `grid`,"
        r" CAST\(ROUND\(DATEDIFF\(CURDATE\(\), `modified`\) / 30\) AS UNSIGNED\) as `num`"
        r" FROM (?P<tablename>datamap_[ns][ew])"
        r" WHERE `grid` > :grid ORDER BY `grid` LIMIT :limit "
    )

    def get_test_data(statement):
        """
        Validate the SQL call and return test data.

        The tablename is extracted from the SQL statement.
        On the first call, the test data, if any, is returned.
        On the second call, an empty list is returned.
        """
        match = re_stmt.match(statement.text)
        assert match
        tablename = match.group("tablename")
        result = Mock(spec_set=("fetchall", "close"))
        try:
            data = test_data[tablename].pop(0)
        except IndexError:
            data = []  # No more data, end DB read loop
        result.fetchall.return_value = data
        return result

    # db_worker_session() returns a context manager
    mock_context = MagicMock(spec_set=("__enter__", "__exit__"))

    # The context manager returns a session
    mock_session = Mock(spec_set=["execute"])
    mock_context.__enter__.return_value = mock_session

    # session.execute(SQL_STATEMENT) returns rows of data
    mock_session.execute.side_effect = get_test_data

    with patch("ichnaea.scripts.datamap.db_worker_session") as mock_db_worker_session:
        mock_db_worker_session.return_value = mock_context
        yield mock_db_worker_session


class TestMap(object):
    def _check_quadtree(self, path):
        assert os.path.isdir(path)
        for name in ("1,0", "meta"):
            assert os.path.isfile(os.path.join(path, name))

    def test_files(self, temp_dir, mock_db_worker_session):
        lines = []
        rows = 0

        csvdir = os.path.join(temp_dir, "csv")
        os.mkdir(csvdir)
        quaddir = os.path.join(temp_dir, "quadtrees")
        os.mkdir(quaddir)
        shapes = os.path.join(temp_dir, "shapes")
        tiles = os.path.join(temp_dir, "tiles")

        expected = {"ne": (0, 0), "nw": (0, 0), "se": (12, 1), "sw": (6, 1)}
        for shard_id, shard in DataMap.shards().items():
            filename = f"map_{shard_id}.csv"
            filepath = os.path.join(csvdir, filename)
            row_count, file_count = export_to_csv(filename, csvdir, shard.__tablename__)
            assert row_count == expected[shard_id][0]
            assert file_count == expected[shard_id][1]

            if not row_count:
                assert not os.path.isfile(filepath)
                continue

            rows += row_count
            with open(filepath, "r") as fd:
                written = fd.read()
            lines.extend([line.split(",") for line in written.split()])

            csv_to_quadtree(filename, csvdir, quaddir)

            quadfolder = os.path.join(quaddir, "map_" + shard_id)
            assert os.path.isdir(quadfolder)
            self._check_quadtree(quadfolder)

        assert rows
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

    def test_multiple_csv(self, temp_dir, raven, mock_db_worker_session):
        """export_to_csv creates multiple CSVs at the file_limit."""

        expected = {"ne": (0, 0), "nw": (0, 0), "se": (12, 2), "sw": (6, 1)}
        csv_dir = os.path.join(temp_dir, "csv")
        os.mkdir(csv_dir)

        for shard_id, shard in DataMap.shards().items():
            filename = f"map_{shard_id}.csv"
            filepath = os.path.join(csv_dir, filename)
            row_count, file_count = export_to_csv(
                filename, csv_dir, shard.__tablename__, file_limit=1
            )
            assert row_count == expected[shard_id][0]
            assert file_count == expected[shard_id][1]

            if not row_count:
                assert not os.path.isfile(filepath)
            elif file_count == 1:
                assert os.path.isfile(filepath)
            else:
                assert not os.path.isfile(filepath)
                for num in range(1, file_count + 1):
                    filename_n = f"submap_{shard_id}_{num:04}.csv"
                    filepath_n = os.path.join(csv_dir, filename_n)
                    assert os.path.isfile(filepath_n)

        quad_dir = os.path.join(temp_dir, "quadtrees")
        os.mkdir(quad_dir)
        with Pool() as pool:
            result = csv_to_quadtrees(pool, csv_dir, quad_dir)
            csv_count, intermediate_quad_count, final_quad_count = result
            assert csv_count == 3
            assert intermediate_quad_count == 2
            assert final_quad_count == 2

    def test_generate(self, temp_dir, raven, mock_db_worker_session):
        """generate() calls the steps for tile generation."""
        result = generate(
            temp_dir,
            "bucket_name",
            raven,
            create=True,
            upload=False,
            concurrency=1,
            max_zoom=2,
        )
        assert set(result.keys()) == {
            "csv_count",
            "csv_converted_count",
            "export_duration_s",
            "intermediate_quadtree_count",
            "merge_duration_s",
            "quadtree_count",
            "quadtree_duration_s",
            "render_duration_s",
            "row_count",
            "tile_count",
        }
        assert result["quadtree_count"] == 2
        assert result["row_count"] == 18
        assert result["tile_count"] == 6
        assert result["csv_count"] == 2
        assert result["csv_converted_count"] == 2
        assert result["intermediate_quadtree_count"] == 0

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
