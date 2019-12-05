"""Database related functionality."""

import os
from contextlib import contextmanager

from alembic.config import main as alembic_main
from pymysql.constants.CLIENT import MULTI_STATEMENTS
from pymysql.err import DatabaseError
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.sql import func, select

from ichnaea.conf import settings


DB_TYPE = {"ro": settings("db_readonly_uri"), "rw": settings("db_readwrite_uri")}


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


def configure_db(type_=None, uri=None, _db=None, pool=True):
    """
    Configure and return a :class:`~ichnaea.db.Database` instance.

    :param type_: one of "ro" or "rw"
    :param uri: the uri to connect to; if not provided, uses ``type_``
        parameter
    :param _db: Test-only hook to provide a pre-configured db.
    :param pool: True for connection pool, False for no connection pool

    """
    if _db is not None:
        return _db
    if uri is None:
        uri = DB_TYPE[type_]
    return Database(uri, pool=pool)


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
        if commit:
            session.begin_nested()
        yield session
        if commit:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


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
                    session.close()
        return response

    return db_tween


class Database(object):
    """A class representing an active database.

    :param uri: A database connection string.
    """

    def __init__(self, uri, pool=True):
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

    def close(self):
        self.engine.pool.dispose()

    def session(self):
        """Return a session for this database."""
        return self.session_factory()

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
    sa_url.database = None
    engine = create_engine(sa_url)
    engine.execute("CREATE DATABASE {} CHARACTER SET = 'utf8'".format(db_to_create))

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
    sa_url.database = None
    engine = create_engine(sa_url)
    engine.execute("DROP DATABASE {}".format(db_to_drop))
