"""Tests for database related functionality."""

import pytest
from pymysql.constants.ER import CONSTRAINT_FAILED, LOCK_WAIT_TIMEOUT, LOCK_DEADLOCK
from pymysql.err import InternalError, MySQLError, OperationalError
from sqlalchemy.exc import InterfaceError, StatementError

from ichnaea.db import retry_on_mysql_lock_fail


class TestDatabase:
    def test_constructor(self, db):
        assert db.engine.name == "mysql"
        assert db.engine.dialect.driver == "pymysql"

    def test_table_creation(self, session):
        result = session.execute("select * from cell_gsm;")
        assert result.first() is None


RETRIABLES = {
    "deadlock": (
        OperationalError,
        LOCK_DEADLOCK,
        "Deadlock found when trying to get lock; try restarting transaction",
    ),
    "wait-timeout": (
        InternalError,
        LOCK_WAIT_TIMEOUT,
        "Lock wait timeout exceeded; try restarting transaction",
    ),
}


class TestRetryOnMySQLLockFail:
    """Test the retry_on_mysql_lock_fail decorator."""

    def _raise_mysql_error(self, errclass, errno, errmsg):
        """Raise a MySQL error wrapped by SQLAlchemy."""
        error = errclass(errno, errmsg)
        wrapped = InterfaceError.instance(
            statement="SELECT COUNT(*) FROM table",
            params={},
            orig=error,
            dbapi_base_err=MySQLError,
        )
        raise wrapped

    @pytest.mark.parametrize(
        "errclass,errno,errmsg", RETRIABLES.values(), ids=list(RETRIABLES.keys())
    )
    def test_retriable_exceptions(self, errclass, errno, errmsg, backoff_sleep_mock):
        """The method is retried on a retriable exception."""
        count = 0

        @retry_on_mysql_lock_fail()
        def raise_first_time():
            nonlocal count
            count += 1
            if count < 2:
                self._raise_mysql_error(errclass, errno, errmsg)

        raise_first_time()
        assert count == 2
        assert backoff_sleep_mock.call_count == 1

    @pytest.mark.parametrize(
        "errclass,errno,errmsg", RETRIABLES.values(), ids=list(RETRIABLES.keys())
    )
    def test_retry_failure(self, errclass, errno, errmsg, backoff_sleep_mock):
        """The retriable exception is raised after several retries."""
        count = 0

        @retry_on_mysql_lock_fail()
        def keep_raising():
            nonlocal count
            count += 1
            self._raise_mysql_error(errclass, errno, errmsg)

        pytest.raises(StatementError, keep_raising)
        assert count == 3
        assert backoff_sleep_mock.call_count == 2

    def test_raises_other_statement_error(self):
        """Non-handled StatementErrors are raised."""

        @retry_on_mysql_lock_fail()
        def raise_other():
            self._raise_mysql_error(
                OperationalError,
                CONSTRAINT_FAILED,
                "CONSTRAINT `CONSTRAINT_1` failed for `table`.`field`",
            )

        pytest.raises(StatementError, raise_other)

    def test_raises_other_exceptions(self):
        """Non-handled exceptions are raised."""

        @retry_on_mysql_lock_fail()
        def raise_other():
            raise RuntimeError("Something else happened.")

        pytest.raises(RuntimeError, raise_other)

    @pytest.mark.parametrize(
        "errclass,errno,errmsg", RETRIABLES.values(), ids=list(RETRIABLES.keys())
    )
    def test_metric_increment(
        self, errclass, errno, errmsg, backoff_sleep_mock, metricsmock
    ):

        count = 0

        @retry_on_mysql_lock_fail(metric="dberror")
        def raise_first_time():
            nonlocal count
            count += 1
            if count < 2:
                self._raise_mysql_error(errclass, errno, errmsg)

        raise_first_time()
        assert count == 2
        assert backoff_sleep_mock.call_count == 1
        metricsmock.assert_incr_once("dberror", tags=[f"errno:{errno}"])

    @pytest.mark.parametrize(
        "errclass,errno,errmsg", RETRIABLES.values(), ids=list(RETRIABLES.keys())
    )
    def test_metric_increment_with_tags(
        self, errclass, errno, errmsg, backoff_sleep_mock, metricsmock
    ):

        count = 0

        @retry_on_mysql_lock_fail(metric="dberror", metric_tags=["weight:heavy"])
        def raise_first_time():
            nonlocal count
            count += 1
            if count < 2:
                self._raise_mysql_error(errclass, errno, errmsg)

        raise_first_time()
        assert count == 2
        assert backoff_sleep_mock.call_count == 1
        metricsmock.assert_incr_once("dberror", tags=[f"errno:{errno}", "weight:heavy"])
