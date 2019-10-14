import pytest

# Use pytest rich asserts in a file that doesn't match test_* pattern
pytest.register_assert_rewrite("ichnaea.api.locate.tests.base")
