from click.testing import CliRunner

from ichnaea.scripts.sentry_test import sentry_test_group


def test_basic():
    """Test that the command imports and runs at all."""
    runner = CliRunner()
    result = runner.invoke(sentry_test_group)
    assert result.exit_code == 0
