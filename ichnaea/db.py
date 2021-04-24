"""Database related functionality."""

import os
from contextlib import contextmanager

from alembic.config import main as alembic_main
import backoff
import markus
from pymysql.constants.CLIENT import MULTI_STATEMENTS
from pymysql.constants.ER import LOCK_WAIT_TIMEOUT, LOCK_DEADLOCK
from pymysql.err import DatabaseError, MySQLError
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import OperationalError, StatementError
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.sql import func, select

from ichnaea.conf import settings


DB_TYPE = {"ro": settings("db_readonly_uri"), "rw": settings("db_readwrite_uri")}
METRICS = markus.get_metrics()


class SqlAlchemyUrlNotSpecified(Exception):
    """Raised when SQLALCHEMY_URL is not specified in environment."""

    def __init__(self, *args, **kwargs):
        super().__init__("SQLALCHEMY_URL is not specified in the environment")


def get_sqlalchemy_url():
    """Returns the ``SQLALCHEMY_URL`` environment value.

    :returns: the sqlalchemy url to be used for alembic migrations

    :raises SqlAlchemyUrlNotSpecified: if ``SQLALCHEMY_URL`` was not specified
        or is an empty string

    """

    url = os.environ.get("SQLALCHEMY_URL", "")
    if not url:
        raise SqlAlchemyUrlNotSpecified()
    return url


def configure_db(type_=None, uri=None, _db=None, pool=True, shared=False):
    """
    Configure and return a :class:`~ichnaea.db.Database` instance.

    :param type_: one of "ro" or "rw"
    :param uri: the uri to connect to; if not provided, uses ``type_``
        parameter
    :param _db: Test-only hook to provide a pre-configured db.
    :param pool: True for connection pool, False for no connection pool
    :param shared: True for a thread-local sessions, False for independent
        sessions
    """
    if _db is not None:
        return _db
    if uri is None:
        uri = DB_TYPE[type_]
    return Database(uri, pool=pool, shared=shared)


# the request db_session and db_tween_factory are inspired by
# pyramid_tm to provide lazy session creation, session closure and
# automatic rollback in case of errors


def db_session(request):
    """Attach a database session to the request."""
    session = getattr(request, "_db_session", None)
    if session is None:
        request._db_session = session = request.registry.db.session()
    return session


@contextmanager
def db_worker_session(database, commit=True):
    """
    Return a database session usable as a context manager.

    :param commit: Should the session be committed or aborted at the end?
    :type commit: bool
    """
    try:
        session = database.session()
        yield session
        if commit:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        database.release_session(session)


def db_tween_factory(handler, registry):
    """A database tween, doing automatic session management."""

    def db_tween(request):
        response = None
        try:
            response = handler(request)
        finally:
            session = getattr(request, "_db_session", None)
            if session is not None:
                # always rollback/close the read-only session
                try:
                    session.rollback()
                except DatabaseError:
                    registry.raven_client.captureException()
                finally:
                    registry.db.release_session(session)
        return response

    return db_tween


class Database:
    """A class representing an active database.

    :param uri: A database connection string.
    :param pool: True for connection pool, False for no connection pool
    :param shared: True for a thread-local sessions, False for independent
    sessions
    """

    def __init__(self, uri, pool=True, shared=False):
        self.uri = uri

        options = {"echo": False, "isolation_level": "REPEATABLE READ"}
        if pool:
            options.update(
                {
                    "poolclass": QueuePool,
                    "pool_pre_ping": True,
                    "pool_recycle": 3600,
                    "pool_size": 10,
                    "pool_timeout": 10,
                    "max_overflow": 10,
                }
            )
        else:
            options.update({"poolclass": NullPool})
        options["connect_args"] = {"charset": "utf8"}
        options["execution_options"] = {"autocommit": False}

        # PyMySQL 0.8 changed for compatibility with mysqlclient
        # Use 0.7's binary prefixes, for selecting and inserting binary data
        options["connect_args"]["binary_prefix"] = True
        # Use 0.7's multiple statements in one execute block, for initial DB setup
        options["connect_args"]["client_flag"] = MULTI_STATEMENTS

        self.engine = create_engine(uri, **options)

        self.session_factory = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )
        self.shared = shared
        if shared:
            self.session_factory = scoped_session(self.session_factory)

    def close(self):
        if self.shared:
            self.session_factory.remove()
        self.engine.pool.dispose()

    def session(self, bind=None):
        """Return a session for this database.

        :param bind: Bind the session to a connection, such as a transaction.
        """
        kwargs = {}
        if bind is not None:
            kwargs["bind"] = bind
        return self.session_factory(**kwargs)

    def release_session(self, session):
        """Release a session for this database."""
        if not self.shared:
            session.close()

    def __repr__(self):
        return self.uri


def ping_session(db_session):
    """Check that a database session is available, using a simple query."""
    try:
        db_session.execute(select([func.now()])).first()
    except OperationalError:
        return False
    else:
        return True


def create_db(uri=None):
    """Create a database specified by uri and setup tables.

    :arg str uri: either None or a valid uri; if None, uses ``SQLALCHEMY_URL``
        environment variable

    :raises sqlalchemy.exc.ProgrammingError: if database already exists
    :raises SqlAlchemyUrlNotSpecified: if ``SQLALCHEMY_URL`` has no value

    Note: This is mysql-specific.

    """
    if uri is None:
        uri = get_sqlalchemy_url()

    sa_url = make_url(uri)
    db_to_create = sa_url.database
    if hasattr(sa_url, "set"):
        # SQLAlchemy 1.4: immutable URL object
        sa_url_no_db = sa_url.set(database="")
    else:
        # SQLAlchemy 1.3: mutate in place
        sa_url_no_db = sa_url
        sa_url_no_db.database = None
    engine = create_engine(sa_url_no_db)
    with engine.connect() as conn:
        conn.execute(f"CREATE DATABASE {db_to_create} CHARACTER SET = 'utf8'")

    alembic_main(["stamp", "base"])
    alembic_main(["upgrade", "head"])


def drop_db(uri=None):
    """Drop database specified in uri.

    Note that the username/password in the specified uri must have permission
    to create/drop databases.

    :arg str uri: either None or a valid uri; if None, uses ``SQLALCHEMY_URL``
        environment variable

    :raises sqlalchemy.exc.InternalError: if database does not exist
    :raises SqlAlchemyUrlNotSpecified: if ``SQLALCHEMY_URL`` has no value

    Note: This is mysql-specific.

    """
    if uri is None:
        uri = get_sqlalchemy_url()

    sa_url = make_url(uri)
    db_to_drop = sa_url.database
    if hasattr(sa_url, "set"):
        # SQLAlchemy 1.4: immutable URL object
        sa_url_no_db = sa_url.set(database="")
    else:
        # SQLAlchemy 1.3: mutate in place
        sa_url_no_db = sa_url
        sa_url_no_db.database = None
    engine = create_engine(sa_url_no_db)
    with engine.connect() as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {db_to_drop}")


def retry_on_mysql_lock_fail(metric=None, metric_tags=None):
    """Function decorator to backoff and retry on MySQL lock failures.

    This handles these MySQL errors:
    * (1205) Lock wait timeout exceeded
    * (1213) Deadlock when trying to get lock

    In both cases, restarting the transaction may work.

    It expects the errors to be wrapped in a SQLAlchemy StatementError, and
    that SQLAlchemy issued a transaction rollback, so it is safe to retry after
    a short sleep. It uses backoff.on_exception to implement the exponential
    backoff.

    Other exceptions are raised, and if limits are met, then the final
    exception is raised as well.

    :arg str metric: An optional counter metric to track handled errors
    :arg list metric_tags: Additional tags to send with the metric
    :return: A function decorator implementing the retry logic
    """

    def is_mysql_lock_error(exception):
        """Is the exception a retryable MySQL lock error?"""
        return (
            isinstance(exception, StatementError)
            and isinstance(exception.orig, MySQLError)
            and exception.orig.args[0] in (LOCK_DEADLOCK, LOCK_WAIT_TIMEOUT)
        )

    def count_exception(exception):
        """Increment the tracking metric for lock errors."""
        tags = ["errno:%s" % exception.orig.args[0]]
        if metric_tags:
            tags.extend(metric_tags)
        METRICS.incr(metric, 1, tags=tags)

    def giveup_handler(exception):
        """Based on this raised exception, should we give up or retry?

        If it is a SQLAlchemy wrapper for a retryable MySQL exception,
        then we should increment a metric and retry.

        If it isn't one of the special exceptions, then give up.
        """
        if is_mysql_lock_error(exception):
            if metric:
                count_exception(exception)
            return False  # Retry if possible
        return True  # Give up on other unknown errors.

    return backoff.on_exception(
        backoff.expo, StatementError, max_tries=3, giveup=giveup_handler
    )
