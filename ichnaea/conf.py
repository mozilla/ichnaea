"""
Application settings and configuration derived from the environment
"""
from __future__ import absolute_import

import os
import os.path

from everett.manager import ConfigManager, ConfigOSEnv, Option

HERE = os.path.dirname(__file__)


def logging_level_parser(value):
    """Validates logging level values."""
    valid_levels = ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG")
    if value not in valid_levels:
        raise ValueError("%s is not a value in %r" % (value, valid_levels))
    return value


class AppComponent:
    """Everett component for configuring Ichnaea"""

    class Config:
        local_dev_env = Option(
            doc=(
                "Whether we are (True) or are not (False) in a local dev"
                " environment. There are some things that get configured one way"
                " in a developer's environment and another way in a server"
                " environment."
            ),
            default="false",
            parser=bool,
        )
        testing = Option(
            doc="Whether or not we are running tests.",
            default="false",
            parser=bool,
        )
        logging_level = Option(
            doc=(
                "Logging level to use. One of CRITICAL, ERROR, WARNING, INFO,"
                " or DEBUG."
            ),
            default="INFO",
            parser=logging_level_parser,
        )
        asset_bucket = Option(
            doc=(
                "name of AWS S3 bucket to store map tile image assets and"
                " export downloads"
            ),
            default="",
        )
        asset_url = Option(
            doc="url for map tile image assets and export downloads",
            default="",
        )

        # Database related settings
        db_readonly_uri = Option(
            doc=(
                "uri for the readonly database; "
                "``mysql+pymysql://USER:PASSWORD@HOST:PORT/NAME``"
            ),
        )
        db_readwrite_uri = Option(
            doc=(
                "uri for the read-write database; "
                "``mysql+pymysql://USER:PASSWORD@HOST:PORT/NAME``"
            ),
        )

        sentry_dsn = Option(
            doc="Sentry DSN; leave blank to disable Sentry error reporting",
            default="",
        )
        statsd_host = Option(doc="StatsD host; blank to disable StatsD", default="")
        statsd_port = Option(default="8125", parser=int, doc="StatsD port")
        redis_uri = Option(doc="uri for Redis; ``redis://HOST:PORT/DB``")
        celery_worker_concurrency = Option(
            doc="the number of concurrent Celery worker processes executing tasks",
            parser=int,
        )
        mapbox_token = Option(
            doc=(
                "Mapbox API key; if you do not provide this, then parts of the "
                "site showing maps will be disabled"
            ),
            default="",
        )
        geoip_path = Option(
            doc="absolute path to mmdb file for GeoIP lookups",
            default=os.path.join(HERE, "tests/data/GeoIP2-City-Test.mmdb"),
        )
        secret_key = Option(
            doc="a unique passphrase used for cryptographic signing",
            default="default for development, change in production",
        )

    def __init__(self, config):
        self.raw_config = config
        self.config = config.with_options(self)

    def __call__(self, *args, **kwargs):
        return self.config(*args, **kwargs)


def build_config_manager():
    config_manager = ConfigManager(
        environments=[
            # Pull configuration from environment variables
            ConfigOSEnv()
        ],
        doc="For configuration help, see https://ichnaea.readthedocs.io/",
    )
    return AppComponent(config_manager)


settings = build_config_manager()


def is_dev_config():
    """Return True if this appears to be the dev environment."""
    dev_redis_uri = "redis://redis:6379/0"
    redis_uri = settings("redis_uri")
    return redis_uri == dev_redis_uri


def check_config():
    """If not in the dev environment, ensure settings are non-development."""
    if is_dev_config():
        return

    issues = []

    # These values should be non-empty and non-default
    should_be_set = {"secret_key"}
    for name in should_be_set:
        default = settings.config.options[name][0].default
        value = settings(name)
        if value == default:
            issues.append(f"{name} has the default value '{value}'")
        elif not value:
            issues.append(f"{name} is not set")

    if issues:
        message = (
            "redis_url has a non-development value, but there are issues"
            " with settings: " + ", ".join(issues)
        )
        raise RuntimeError(message)
