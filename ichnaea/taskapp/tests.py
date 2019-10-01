from inspect import getmembers

from celery import signals

from ichnaea.taskapp.task import BaseTask


class TestBeat(object):
    def test_tasks(self, celery, tmpdir):
        filename = str(tmpdir / "celerybeat-schedule")
        beat_app = celery.Beat()
        beat = beat_app.Service(app=celery, schedule_filename=filename)
        signals.beat_init.send(sender=beat)

        # Parses the schedule as a side-effect
        scheduler = beat.get_scheduler()
        registered_tasks = set(scheduler._store["entries"].keys())

        # Import tasks after beat startup, to ensure beat_init correctly loads
        # configured Celery imports.
        from ichnaea.data import tasks

        all_tasks = set(
            [m[1].shortname() for m in getmembers(tasks) if isinstance(m[1], BaseTask)]
        )

        assert all_tasks - registered_tasks == set(
            [
                "data.update_blue",
                "data.update_cell",
                "data.update_wifi",
                "data.update_datamap",
                "data.cleanup_datamap",
                "data.cell_export_diff",
                "data.cell_export_full",
                "data.export_reports",
                "data.load_cellarea",
            ]
        )

        assert registered_tasks - all_tasks == set(
            [
                "data.cleanup_datamap_ne",
                "data.cleanup_datamap_nw",
                "data.cleanup_datamap_se",
                "data.cleanup_datamap_sw",
                "data.update_blue_0",
                "data.update_blue_1",
                "data.update_blue_2",
                "data.update_blue_3",
                "data.update_blue_4",
                "data.update_blue_5",
                "data.update_blue_6",
                "data.update_blue_7",
                "data.update_blue_8",
                "data.update_blue_9",
                "data.update_blue_a",
                "data.update_blue_b",
                "data.update_blue_c",
                "data.update_blue_d",
                "data.update_blue_e",
                "data.update_blue_f",
                "data.update_cell_gsm",
                "data.update_cell_lte",
                "data.update_cell_wcdma",
                "data.update_datamap_ne",
                "data.update_datamap_nw",
                "data.update_datamap_se",
                "data.update_datamap_sw",
                "data.update_wifi_0",
                "data.update_wifi_1",
                "data.update_wifi_2",
                "data.update_wifi_3",
                "data.update_wifi_4",
                "data.update_wifi_5",
                "data.update_wifi_6",
                "data.update_wifi_7",
                "data.update_wifi_8",
                "data.update_wifi_9",
                "data.update_wifi_a",
                "data.update_wifi_b",
                "data.update_wifi_c",
                "data.update_wifi_d",
                "data.update_wifi_e",
                "data.update_wifi_f",
            ]
        )

        for i in range(16):
            assert "data.update_blue_%x" % i in registered_tasks
        for name in ("gsm", "wcdma", "lte"):
            assert "data.update_cell_" + name in registered_tasks
        for i in range(16):
            assert "data.update_wifi_%x" % i in registered_tasks


class TestWorkerConfig(object):
    def test_config(self, celery):
        assert celery.conf["task_always_eager"]
        assert "redis" in celery.conf["result_backend"]
