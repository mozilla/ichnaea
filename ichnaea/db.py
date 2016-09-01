"""Database related functionality."""

from contextlib import contextmanager
from pymysql.err import DatabaseError

from sqlalchemy import (
    create_engine,
    exc,
    event,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.pool import NullPool, Pool, QueuePool
from sqlalchemy.sql import func, select
from sqlalchemy.sql.expression import Insert

from ichnaea.config import (
    DB_DDL_URI,
    DB_RW_URI,
    DB_RO_URI,
)


@compiles(Insert, 'mysql')
def on_duplicate(insert, compiler, **kw):
    """Custom MySQL insert on_duplicate support."""
    stmt = compiler.visit_insert(insert, **kw)
    my_var = insert.dialect_kwargs.get('mysql_on_duplicate', None)
    if my_var:
        stmt += ' ON DUPLICATE KEY UPDATE %s' % my_var
    return stmt

Insert.argument_for('mysql', 'on_duplicate', None)


def configure_db(uri, pool=True, _db=None):
    """
    Configure and return a :class:`~ichnaea.db.Database` instance.

    :param _db: Test-only hook to provide a pre-configured db.
    """
    if _db is not None:
        return _db
    return Database(uri, pool=pool)


def configure_ddl_db(uri=DB_DDL_URI, _db=None):
    return configure_db(uri=uri, pool=False, _db=_db)


def configure_rw_db(uri=DB_RW_URI, _db=None):
    return configure_db(uri=uri, _db=_db)


def configure_ro_db(uri=DB_RO_URI, _db=None):
    return configure_db(uri=uri, _db=_db)


# the request db_ro_session and db_tween_factory are inspired by
# pyramid_tm to provide lazy session creation, session closure and
# automatic rollback in case of errors

def db_ro_session(request):
    """Attach a database read-only session to the request."""
    session = getattr(request, '_db_ro_session', None)
    if session is None:
        db = request.registry.db_ro
        request._db_ro_session = session = db.session()
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
    except Exception:  # pragma: no cover
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
            ro_session = getattr(request, '_db_ro_session', None)
            if ro_session is not None:
                # always rollback/close the `read-only` ro sessions
                try:
                    ro_session.rollback()
                except DatabaseError:  # pragma: no cover
                    registry.raven_client.captureException()
                finally:
                    ro_session.close()
        return response

    return db_tween


class Database(object):
    """A class representing an active database.

    :param uri: A database connection string.
    """

    def __init__(self, uri, pool=True):
        options = {
            'echo': False,
            'isolation_level': 'REPEATABLE READ',
        }
        if pool:
            options.update({
                'poolclass': QueuePool,
                'pool_recycle': 3600,
                'pool_size': 10,
                'pool_timeout': 10,
                'max_overflow': 10,
            })
        else:
            options.update({
                'poolclass': NullPool,
            })
        options['connect_args'] = {'charset': 'utf8'}
        options['execution_options'] = {'autocommit': False}
        self.engine = create_engine(uri, **options)

        self.session_factory = sessionmaker(
            bind=self.engine, class_=PingableSession,
            autocommit=False, autoflush=False)

    def close(self):
        self.engine.pool.dispose()

    def ping(self):
        """
        Check database connectivity.
        On success returns `True`, otherwise `False`.
        """
        with db_worker_session(self, commit=False) as session:
            success = session.ping()
        return success

    def session(self):
        """Return a session for this database."""
        return self.session_factory()


class PingableSession(Session):
    """A custom pingable database session."""

    def __init__(self, *args, **kw):
        # disable automatic docstring
        return super(PingableSession, self).__init__(*args, **kw)

    def ping(self):
        """Use this active session to check the database connectivity."""
        try:
            self.execute(select([func.now()])).first()
        except exc.OperationalError:
            return False
        return True


@event.listens_for(Pool, 'checkout')
def check_connection(dbapi_conn, conn_record, conn_proxy):
    """
    Listener for pool checkout events that pings every connection before
    using it. Implements the `pessimistic disconnect handling strategy
    <https://docs.sqlalchemy.org/en/latest/core/pooling.html#disconnect-handling-pessimistic>`_.
    """
    try:
        # dbapi_con.ping() ends up calling mysql_ping()
        # http://dev.mysql.com/doc/refman/5.6/en/mysql-ping.html
        dbapi_conn.ping(reconnect=True)
    except exc.OperationalError as ex:  # pragma: no cover
        if ex.args[0] in (2003,     # Connection refused
                          2006,     # MySQL server has gone away
                          2013,     # Lost connection to MySQL server
                                    # during query
                          2055):    # Lost connection to MySQL server at '%s',
                                    # system error: %d
            # caught by pool, which will retry with a new connection
            raise exc.DisconnectionError()
        else:
            raise
