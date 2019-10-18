from collections import defaultdict
import json
import re
import time
from urllib.parse import urlparse
import uuid

import boto3
import boto3.exceptions
import botocore.exceptions
import markus
import redis.exceptions
import requests
import requests.exceptions
from sqlalchemy import select
import sqlalchemy.exc

from ichnaea.data import _map_content_enabled
from ichnaea.models import (
    ApiKey,
    BlueObservation,
    BlueReport,
    BlueShard,
    CellObservation,
    CellReport,
    CellShard,
    DataMap,
    ExportConfig,
    Report,
    WifiObservation,
    WifiReport,
    WifiShard,
)
from ichnaea.models.content import encode_datamap_grid
from ichnaea import util


WHITESPACE = re.compile(r"\s", flags=re.UNICODE)

METRICS = markus.get_metrics()


class IncomingQueue(object):
    """
    The incoming queue contains the data collected in the web application. It
    is the single entrypoint from which all other data pipelines get their
    data.

    It distributes the data into the configured export queues, checks those
    queues and if they contain enough or old enough data schedules an async
    export task to process the data in each queue.

    """

    def __init__(self, task):
        self.task = task

    def __call__(self, export_task):
        redis_client = self.task.redis_client
        data_queue = self.task.app.data_queues["update_incoming"]
        data = data_queue.dequeue()

        grouped = defaultdict(list)
        for item in data:
            grouped[(item["api_key"], item.get("source", "gnss"))].append(
                {"api_key": item["api_key"], "report": item["report"]}
            )

        with self.task.db_session(commit=False) as session:
            export_configs = ExportConfig.all(session)

        with self.task.redis_pipeline() as pipe:
            for (api_key, source), items in grouped.items():
                for config in export_configs:
                    if config.allowed(api_key, source):
                        queue_key = config.queue_key(api_key, source)
                        queue = config.queue(queue_key, redis_client)
                        queue.enqueue(items, pipe=pipe)

        for config in export_configs:
            # Check all queues if they now contain enough data or
            # old enough data to be ready for processing.
            for queue_key in config.partitions(redis_client):
                queue = config.queue(queue_key, redis_client)
                if queue.ready():
                    export_task.delay(config.name, queue_key)

        if data_queue.ready():
            self.task.apply_countdown()


class ReportExporter(object):

    _retriable = (IOError,)
    _retries = 3
    _retry_wait = 1.0

    def __init__(self, task, config, queue_key):
        self.task = task
        self.config = config
        self.queue_key = queue_key
        self.queue = config.queue(queue_key, task.redis_client)
        self.stats_tags = ["key:" + self.config.name]

    @staticmethod
    def export(task, name, queue_key):
        with task.db_session(commit=False) as session:
            config = ExportConfig.get(session, name)

        exporter_types = {
            "dummy": DummyExporter,
            "geosubmit": GeosubmitExporter,
            "internal": InternalExporter,
            "s3": S3Exporter,
        }
        exporter_type = exporter_types.get(config.schema)
        if exporter_type is not None:
            exporter_type(task, config, queue_key)()

    def __call__(self):
        queue_items = self.queue.dequeue()
        if not queue_items:
            return

        success = False
        for i in range(self._retries):
            try:
                with METRICS.timer("data.export.upload.timing", tags=self.stats_tags):
                    self.send(queue_items)

                success = True
            except self._retriable:
                success = False
                time.sleep(self._retry_wait * (i ** 2 + 1))

            if success:
                METRICS.incr("data.export.batch", tags=self.stats_tags)
                break

        if success and self.queue.ready():
            self.task.apply_countdown(args=[self.config.name, self.queue_key])

    def send(self, queue_items):
        raise NotImplementedError()


class DummyExporter(ReportExporter):
    def send(self, queue_items):
        pass


class GeosubmitExporter(ReportExporter):

    _retriable = (IOError, requests.exceptions.RequestException)

    def send(self, queue_items):
        # ignore metadata
        reports = [item["report"] for item in queue_items]

        headers = {
            "Content-Encoding": "gzip",
            "Content-Type": "application/json",
            "User-Agent": "ichnaea",
        }

        response = requests.post(
            self.config.url,
            data=util.encode_gzip(json.dumps({"items": reports}), compresslevel=5),
            headers=headers,
            timeout=60.0,
        )

        # log upload_status and trigger exception for bad responses
        # this causes the task to be re-tried
        METRICS.incr(
            "data.export.upload",
            tags=self.stats_tags + ["status:%s" % response.status_code],
        )
        response.raise_for_status()


class S3Exporter(ReportExporter):

    _retriable = (
        IOError,
        boto3.exceptions.Boto3Error,
        botocore.exceptions.BotoCoreError,
    )

    def send(self, queue_items):
        # ignore metadata
        reports = [item["report"] for item in queue_items]

        _, bucketname, path = urlparse(self.config.url)[:3]
        # s3 key names start without a leading slash
        path = path.lstrip("/")
        if not path.endswith("/"):
            path += "/"

        year, month, day = util.utcnow().timetuple()[:3]

        # strip away queue prefix again
        parts = self.queue_key.split(":")
        source = parts[1]
        api_key = parts[2]

        obj_name = path.format(
            source=source, api_key=api_key, year=year, month=month, day=day
        )
        obj_name += uuid.uuid1().hex + ".json.gz"

        try:
            data = util.encode_gzip(json.dumps({"items": reports}), compresslevel=7)

            s3 = boto3.resource("s3")
            bucket = s3.Bucket(bucketname)

            obj = bucket.Object(obj_name)
            obj.put(Body=data, ContentEncoding="gzip", ContentType="application/json")

            METRICS.incr(
                "data.export.upload", tags=self.stats_tags + ["status:success"]
            )
        except Exception:
            METRICS.incr(
                "data.export.upload", tags=self.stats_tags + ["status:failure"]
            )
            raise


class InternalTransform(object):
    """
    This maps the geosubmit v2 schema used in view code and external
    transfers (backup, forward to partners) to the internal submit v1
    schema used in our own database models.
    """

    # *_id maps a source section id to a target section id
    # *_map maps fields inside the section from source to target id
    # if the names are equal, a simple string can be specified instead
    # of a two-tuple

    position_id = ("position", None)
    position_map = [
        ("latitude", "lat"),
        ("longitude", "lon"),
        "accuracy",
        "altitude",
        ("altitudeAccuracy", "altitude_accuracy"),
        "heading",
        "pressure",
        "speed",
        "source",
    ]

    blue_id = ("bluetoothBeacons", "blue")
    blue_map = [("macAddress", "mac"), "age", ("signalStrength", "signal")]

    cell_id = ("cellTowers", "cell")
    cell_map = [
        ("radioType", "radio"),
        ("mobileCountryCode", "mcc"),
        ("mobileNetworkCode", "mnc"),
        ("locationAreaCode", "lac"),
        ("cellId", "cid"),
        "age",
        "asu",
        ("primaryScramblingCode", "psc"),
        "serving",
        ("signalStrength", "signal"),
        ("timingAdvance", "ta"),
    ]

    wifi_id = ("wifiAccessPoints", "wifi")
    wifi_map = [
        ("macAddress", "mac"),
        "age",
        "channel",
        "frequency",
        ("radioType", "radio"),
        ("signalToNoiseRatio", "snr"),
        ("signalStrength", "signal"),
    ]

    def _map_dict(self, item_source, field_map):
        value = {}
        for spec in field_map:
            if isinstance(spec, tuple):
                source, target = spec
            else:
                source = spec
                target = spec
            source_value = item_source.get(source)
            if source_value is not None:
                value[target] = source_value
        return value

    def _parse_dict(self, item, report, key_map, field_map):
        value = {}
        item_source = item.get(key_map[0])
        if item_source:
            value = self._map_dict(item_source, field_map)
        if value:
            if key_map[1] is None:
                report.update(value)
            else:
                report[key_map[1]] = value
        return value

    def _parse_list(self, item, report, key_map, field_map):
        values = []
        for value_item in item.get(key_map[0], ()):
            value = self._map_dict(value_item, field_map)
            if value:
                values.append(value)
        if values:
            report[key_map[1]] = values
        return values

    def __call__(self, item):
        report = {}
        self._parse_dict(item, report, self.position_id, self.position_map)

        blues = self._parse_list(item, report, self.blue_id, self.blue_map)
        cells = self._parse_list(item, report, self.cell_id, self.cell_map)
        wifis = self._parse_list(item, report, self.wifi_id, self.wifi_map)

        gps_age = item.get("position", {}).get("age", 0)
        timestamp = item.get("timestamp")
        if timestamp:
            # turn timestamp into GPS timestamp
            report["timestamp"] = timestamp - gps_age

        if gps_age:
            # Normalize age fields to be relative to GPS time
            for type_ in ("blue", "cell", "wifi"):
                for record in report.get(type_, ()):
                    record["age"] = record.get("age", 0) - gps_age

        if blues or cells or wifis:
            return report
        return {}


class InternalExporter(ReportExporter):

    _retriable = (IOError, redis.exceptions.RedisError, sqlalchemy.exc.InternalError)
    transform = InternalTransform()

    def send(self, queue_items):
        api_keys = set()
        api_keys_known = set()
        metrics = {}

        items = []
        for item in queue_items:
            # preprocess items and extract set of API keys
            item["report"] = self.transform(item["report"])
            if item["report"]:
                items.append(item)
                api_keys.add(item["api_key"])

        for api_key in api_keys:
            metrics[api_key] = {}
            for type_ in ("report", "blue", "cell", "wifi"):
                for action in ("drop", "upload"):
                    metrics[api_key]["%s_%s" % (type_, action)] = 0

        with self.task.db_session(commit=False) as session:
            # limit database session to get API keys
            keys = [key for key in api_keys if key]
            if keys:
                columns = ApiKey.__table__.c
                rows = session.execute(
                    select([columns.valid_key]).where(columns.valid_key.in_(keys))
                ).fetchall()

                for row in rows:
                    api_keys_known.add(row.valid_key)

        positions = []
        observations = {"blue": [], "cell": [], "wifi": []}

        for item in items:
            api_key = item["api_key"]
            report = item["report"]

            obs, malformed_obs = self.process_report(report)

            any_data = False
            for name in ("blue", "cell", "wifi"):
                if obs.get(name):
                    observations[name].extend(obs[name])
                    metrics[api_key][name + "_upload"] += len(obs[name])
                    any_data = True
                metrics[api_key][name + "_drop"] += malformed_obs.get(name, 0)

            metrics[api_key]["report_upload"] += 1
            if any_data:
                positions.append((report["lat"], report["lon"]))
            else:
                metrics[api_key]["report_drop"] += 1

        with self.task.redis_pipeline() as pipe:
            self.queue_observations(pipe, observations)
            if _map_content_enabled and positions:
                self.process_datamap(pipe, positions)

        self.emit_metrics(api_keys_known, metrics)

    def queue_observations(self, pipe, observations):
        for datatype, shard_model, shard_key, queue_prefix in (
            ("blue", BlueShard, "mac", "update_blue_"),
            ("cell", CellShard, "cellid", "update_cell_"),
            ("wifi", WifiShard, "mac", "update_wifi_"),
        ):

            queued_obs = defaultdict(list)
            for obs in observations[datatype]:
                # group by sharded queue
                shard_id = shard_model.shard_id(getattr(obs, shard_key))
                queue_id = queue_prefix + shard_id
                queued_obs[queue_id].append(obs.to_json())

            for queue_id, values in queued_obs.items():
                # enqueue values for each queue
                queue = self.task.app.data_queues[queue_id]
                queue.enqueue(values, pipe=pipe)

    def emit_metrics(self, api_keys_known, metrics):
        for api_key, key_metrics in metrics.items():
            api_tag = []
            if api_key and api_key in api_keys_known:
                api_tag = ["key:%s" % api_key]

            for name, count in key_metrics.items():
                if not count:
                    continue

                type_, action = name.split("_")
                if type_ == "report":
                    suffix = "report"
                    tags = api_tag
                else:
                    suffix = "observation"
                    tags = ["type:%s" % type_] + api_tag

                METRICS.incr("data.%s.%s" % (suffix, action), count, tags=tags)

    def process_report(self, data):
        report = Report.create(**data)
        if report is None:
            return ({}, {})

        malformed = {}
        observations = {}
        for name, report_cls, obs_cls in (
            ("blue", BlueReport, BlueObservation),
            ("cell", CellReport, CellObservation),
            ("wifi", WifiReport, WifiObservation),
        ):

            malformed[name] = 0
            observations[name] = {}

            if data.get(name):
                for item in data[name]:
                    # validate the blue/cell/wifi specific fields
                    item_report = report_cls.create(**item)
                    if item_report is None:
                        malformed[name] += 1
                        continue

                    # combine general and specific report data into one
                    item_obs = obs_cls.combine(report, item_report)
                    item_key = item_obs.unique_key

                    # if we have better data for the same key, ignore
                    existing = observations[name].get(item_key)
                    if existing is not None and existing.better(item_obs):
                        continue

                    observations[name][item_key] = item_obs

        obs = {
            "blue": observations["blue"].values(),
            "cell": observations["cell"].values(),
            "wifi": observations["wifi"].values(),
        }
        return (obs, malformed)

    def process_datamap(self, pipe, positions):
        grids = set()
        for lat, lon in positions:
            if lat is not None and lon is not None:
                grids.add(DataMap.scale(lat, lon))

        shards = defaultdict(set)
        for lat, lon in grids:
            shards[DataMap.shard_id(lat, lon)].add(encode_datamap_grid(lat, lon))

        for shard_id, values in shards.items():
            queue = self.task.app.data_queues["update_datamap_" + shard_id]
            queue.enqueue(list(values), pipe=pipe)
