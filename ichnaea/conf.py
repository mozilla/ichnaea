"""
Application settings and configuration derived from the environment
"""
from __future__ import absolute_import

import os
import os.path

from everett.component import ConfigOptions, RequiredConfigMixin
from everett.manager import ConfigManager, ConfigOSEnv

HERE = os.path.dirname(__file__)


class AppConfig(RequiredConfigMixin):
    required_config = ConfigOptions()
    required_config.add_option(
        "local_dev_env",
        default="false",
        parser=bool,
        doc=(
            "Whether (True) or not (False) we are in a local dev environment. "
            "There are some things that get configured one way in a developer's "
            "environment and another way in a server environment."
        ),
    )
    required_config.add_option(
        "testing",
        default="false",
        parser=bool,
        doc="Whether or not we are running tests.",
    )

    required_config.add_option(
        "asset_bucket",
        default="",
        doc="name of AWS S3 bucket to store map tile image assets and export downloads",
    )
    required_config.add_option(
        "asset_url",
        default="",
        doc="url for map tile image assets and export downloads",
    )

    # Database related settings
    required_config.add_option(
        "db_readonly_uri",
        doc=(
            "uri for the readonly database; "
            "``mysql+pymysql://USER:PASSWORD@HOST:PORT/NAME``"
        ),
    )
    required_config.add_option(
        "db_readwrite_uri",
        doc=(
            "uri for the read-write database; "
            "``mysql+pymysql://USER:PASSWORD@HOST:PORT/NAME``"
        ),
    )
    required_config.add_option(
        "db_ddl_uri",
        doc=(
            "uri for the ddl database used for migrations; "
            "``mysql+pymysql://USER:PASSWORD@HOST:PORT/NAME``"
        ),
    )

    required_config.add_option(
        "sentry_dsn",
        default="",
        doc="Sentry DSN; leave blank to disable Sentry error reporting",
    )

    required_config.add_option(
        "statsd_host", default="", doc="StatsD host; blank to disable StatsD"
    )

    required_config.add_option(
        "redis_uri", doc="uri for Redis; ``redis://HOST:PORT/DB``"
    )

    required_config.add_option(
        "mapbox_token",
        default="",
        doc=(
            "Mapbox API key; if you do not provide this, then parts of the "
            "site showing maps will be disabled"
        ),
    )

    required_config.add_option(
        "geoip_path",
        default=os.path.join(HERE, "tests/data/GeoIP2-City-Test.mmdb"),
        doc="absolute path to mmdb file for GeoIP lookups",
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
    return AppConfig(config_manager)


settings = build_config_manager()
