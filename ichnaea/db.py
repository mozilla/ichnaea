from contextlib import contextmanager

from sqlalchemy import (
    create_engine,
    exc,
    event,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.pool import Pool
from sqlalchemy.sql import func, select
from sqlalchemy.sql.expression import Insert

_Model = declarative_base()


@compiles(Insert)
def on_duplicate(insert, compiler, **kw):
    s = compiler.visit_insert(insert, **kw)
    if 'on_duplicate' in insert.kwargs:
        return s + " ON DUPLICATE KEY UPDATE " + insert.kwargs['on_duplicate']
    return s


# the request db_sessions and db_tween_factory are inspired by pyramid_tm
# to provide lazy session creation, session closure and automatic
# rollback in case of errors

def db_master_session(request):  # pragma: no cover
    session = getattr(request, '_db_master_session', None)
    if session is None:
        db = request.registry.db_master
        request._db_master_session = session = db.session()
    return session


def db_slave_session(request):
    session = getattr(request, '_db_slave_session', None)
    if session is None:
        db = request.registry.db_slave
        request._db_slave_session = session = db.session()
    return session


@contextmanager
def db_worker_session(database):
    try:
        session = database.session()
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def db_tween_factory(handler, registry):

    def db_tween(request):
        response = None
        try:
            response = handler(request)
        finally:
            master_session = getattr(request, '_db_master_session', None)
            if master_session is not None:  # pragma: no cover
                # only deal with requests with a session
                if response is not None and \
                   response.status.startswith(('4', '5')):
                    # never commit on error
                    master_session.rollback()
                master_session.close()

            slave_session = getattr(request, '_db_slave_session', None)
            if slave_session is not None:
                # always rollback/close the `read-only` slave sessions
                if request.registry.db_master != request.registry.db_slave:
                    # The db_master and db_slave will only be the same
                    # during tests.
                    try:
                        slave_session.rollback()
                    finally:
                        slave_session.close()
        return response

    return db_tween


class Database(object):

    def __init__(self, uri):
        options = {
            'pool_recycle': 3600,
            'pool_size': 10,
            'pool_timeout': 10,
            'max_overflow': 10,
            'echo': False,
            'isolation_level': 'REPEATABLE READ',
        }
        options['connect_args'] = {'charset': 'utf8'}
        options['execution_options'] = {'autocommit': False}
        self.engine = create_engine(uri, **options)

        self.session_factory = sessionmaker(
            bind=self.engine, class_=HookedSession,
            autocommit=False, autoflush=False)

    def ping(self):  # pragma: no cover
        with db_worker_session(self) as session:
            success = session.ping()
        return success

    def session(self):
        return self.session_factory()


class HookedSession(Session):

    def on_post_commit(self, function, *args, **kw):
        """
        Register a post commit (after-transaction-end) hook.

        The function will be called with all the arguments and keywords
        arguments preceded by a single session argument.
        """
        def wrapper(session, transaction):
            return function(session, *args, **kw)

        event.listen(self, 'after_transaction_end', wrapper, once=True)

    def ping(self):
        try:
            self.execute(select([func.now()])).first()
        except exc.OperationalError:
            return False
        return True


@event.listens_for(Pool, "checkin")
def clear_result_on_pool_checkin(conn, conn_record):
    """
    PyMySQL Connection objects hold a reference to their most recent
    Result object, which can cause large datasets to remain in memory.
    Explicitly clear it when returning a connection to the pool.
    """
    if conn and conn._result:
        conn._result = None


@event.listens_for(Pool, "checkout")
def check_connection(dbapi_conn, conn_record, conn_proxy):
    '''
    Listener for Pool checkout events that pings every connection before using.
    Implements pessimistic disconnect handling strategy. See also:
    http://docs.sqlalchemy.org/en/rel_0_9/core/pooling.html#disconnect-handling-pessimistic
    '''
    try:
        # dbapi_con.ping() ends up calling mysql_ping()
        # http://dev.mysql.com/doc/refman/5.6/en/mysql-ping.html
        dbapi_conn.ping(reconnect=False)
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
