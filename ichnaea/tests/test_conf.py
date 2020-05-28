"""Tests for ichnaea.conf"""

from unittest import mock

from everett.manager import config_override
import pytest

from ichnaea.conf import check_config, is_dev_config


class TestIsDevConfig:
    """Tests for ichnaea.conf.is_dev_config()"""

    def test_testing(self):
        """The testing config is non-development."""
        assert not is_dev_config()

    def test_is_dev(self):
        """The REDIS_URI is used to determine if we're in development."""
        with config_override(REDIS_URI="redis://redis:6379/0"):
            assert is_dev_config()


SECRET_KEY_DEFAULT = "default for development, change in production"


class TestCheckConfig:
    """Tests for ichnaea.conf.check_config()"""

    def test_testing(self):
        """The testing configuration passes."""
        check_config()

    @pytest.mark.parametrize("secret_key", ("", SECRET_KEY_DEFAULT, "other"))
    def test_dev_any_secret_key(self, secret_key):
        with mock.patch("ichnaea.conf.is_dev_config", return_value=True):
            with config_override(SECRET_KEY=secret_key):
                check_config()

    def test_not_dev_fails_with_blank_secret_key(self):
        with mock.patch("ichnaea.conf.is_dev_config", return_value=False):
            with config_override(SECRET_KEY=""):
                with pytest.raises(RuntimeError) as e:
                    check_config()
                assert e.value.args[0].endswith("secret_key is not set")

    def test_not_dev_fails_with_default_key(self):
        with mock.patch("ichnaea.conf.is_dev_config", return_value=False):
            with config_override(SECRET_KEY=SECRET_KEY_DEFAULT):
                with pytest.raises(RuntimeError) as e:
                    check_config()
                expected = f"secret_key has the default value '{SECRET_KEY_DEFAULT}'"
                assert e.value.args[0].endswith(expected)
