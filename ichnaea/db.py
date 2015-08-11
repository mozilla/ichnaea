"""Database related functionality."""

from contextlib import contextmanager
from functools import partial
import warnings

from pymysql._compat import text_type
from pymysql import cursors
from pymysql import err
from six import PY2
from sqlalchemy import (
    create_engine,
    exc,
    event,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.pool import Pool
from sqlalchemy.sql import func, select
from sqlalchemy.sql.expression import Insert


# Backport from unreleased PyMySQL 0.6.7
# https://github.com/PyMySQL/PyMySQL/issues/343
def _show_warnings(self, conn):  # pragma: no cover
    if self._result and self._result.has_next:
        return
    ws = conn.show_warnings()
    if ws is None:
        return
    for w in ws:
        msg = w[-1]
        if PY2:
            if isinstance(msg, unicode):
                msg = msg.encode('utf-8', 'replace')
        warnings.warn(str(msg), err.Warning, 4)


cursors.Cursor._show_warnings = _show_warnings


def _ensure_bytes(self, x, encoding=None):  # pragma: no cover
    if not PY2:
        return x
    if isinstance(x, unicode):
        x = x.encode(encoding)
    elif isinstance(x, (tuple, list)):
        x = type(x)(self._ensure_bytes(v, encoding=encoding) for v in x)
    return x


def _escape_args(self, args, conn):  # pragma: no cover
    ensure_bytes = partial(self._ensure_bytes, encoding=conn.encoding)

    if isinstance(args, (tuple, list)):
        if PY2:
            args = tuple(map(ensure_bytes, args))
        return tuple(conn.escape(arg) for arg in args)
    elif isinstance(args, dict):
        if PY2:
            args = dict((ensure_bytes(key), ensure_bytes(val)) for
                        (key, val) in args.items())
        return dict((key, conn.escape(val)) for (key, val) in args.items())
    else:
        # If it's not a dictionary let's try escaping it anyways.
        # Worst case it will throw a Value error
        if PY2:
            ensure_bytes(args)
        return conn.escape(args)


def mogrify(self, query, args=None):  # pragma: no cover
    """
    Returns the exact string that is sent to the database by calling the
    execute() method.

    This method follows the extension to the DB API 2.0 followed by Psycopg.
    """
    conn = self._get_db()
    if PY2:  # Use bytes on Python 2 always
        query = self._ensure_bytes(query, encoding=conn.encoding)

    if args is not None:
        query = query % self._escape_args(args, conn)

    return query


def execute(self, query, args=None):  # pragma: no cover
    '''Execute a query'''
    while self.nextset():
        pass

    query = self.mogrify(query, args)

    result = self._query(query)
    self._executed = query
    return result


def executemany(self, query, args):  # pragma: no cover
    """Run several data against one query

    PyMySQL can execute bulkinsert for query like 'INSERT ... VALUES (%s)'.
    In other form of queries, just run :meth:`execute` many times.
    """
    if not args:
        return

    m = cursors.RE_INSERT_VALUES.match(query)
    if m:
        q_prefix = m.group(1)
        q_values = m.group(2).rstrip()
        q_postfix = m.group(3) or ''
        assert q_values[0] == '(' and q_values[-1] == ')'
        return self._do_execute_many(q_prefix, q_values, q_postfix, args,
                                     self.max_stmt_length,
                                     self._get_db().encoding)

    self.rowcount = sum(self.execute(query, arg) for arg in args)
    return self.rowcount


def _do_execute_many(self, prefix, values, postfix, args,
                     max_stmt_length, encoding):  # pragma: no cover
    conn = self._get_db()
    escape = self._escape_args
    if isinstance(prefix, text_type):
        prefix = prefix.encode(encoding)
    if PY2 and isinstance(values, text_type):
        values = values.encode(encoding)
    if isinstance(postfix, text_type):
        postfix = postfix.encode(encoding)
    sql = bytearray(prefix)
    args = iter(args)
    v = values % escape(next(args), conn)
    if isinstance(v, text_type):
        if PY2:
            v = v.encode(encoding)
        else:
            v = v.encode(encoding, 'surrogateescape')
    sql += v
    rows = 0
    for arg in args:
        v = values % escape(arg, conn)
        if isinstance(v, text_type):
            if PY2:
                v = v.encode(encoding)
            else:
                v = v.encode(encoding, 'surrogateescape')
        if len(sql) + len(v) + len(postfix) + 1 > max_stmt_length:
            rows += self.execute(sql + postfix)
            sql = bytearray(prefix)
        else:
            sql += b','
        sql += v
    rows += self.execute(sql + postfix)
    self.rowcount = rows
    return rows


cursors.Cursor._ensure_bytes = _ensure_bytes
cursors.Cursor._escape_args = _escape_args
cursors.Cursor.mogrify = mogrify
cursors.Cursor.execute = execute
cursors.Cursor.executemany = executemany
cursors.Cursor._do_execute_many = _do_execute_many


@compiles(Insert, 'mysql')
def on_duplicate(insert, compiler, **kw):
    """Custom MySQL insert on_duplicate support."""
    stmt = compiler.visit_insert(insert, **kw)
    my_var = insert.dialect_kwargs.get('mysql_on_duplicate', None)
    if my_var:
        stmt += ' ON DUPLICATE KEY UPDATE %s' % my_var
    return stmt

Insert.argument_for('mysql', 'on_duplicate', None)


def configure_db(uri, _db=None):
    """
    Configure and return a :class:`~ichnaea.db.Database` instance.

    :param _db: Test-only hook to provide a pre-configured db.
    """
    if _db is not None:
        return _db
    return Database(uri)


# the request db_sessions and db_tween_factory are inspired by pyramid_tm
# to provide lazy session creation, session closure and automatic
# rollback in case of errors

def db_rw_session(request):  # pragma: no cover
    """Attach a database read/write session to the request."""
    session = getattr(request, '_db_rw_session', None)
    if session is None:
        db = request.registry.db_rw
        request._db_rw_session = session = db.session()
    return session


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
            rw_session = getattr(request, '_db_rw_session', None)
            if rw_session is not None:  # pragma: no cover
                # only deal with requests with a session
                if response is not None and \
                   response.status.startswith(('4', '5')):
                    # never commit on error
                    rw_session.rollback()
                rw_session.close()

            ro_session = getattr(request, '_db_ro_session', None)
            if ro_session is not None:
                # always rollback/close the `read-only` ro sessions
                if request.registry.db_rw != request.registry.db_ro:
                    # The db_rw and db_ro will only be the same
                    # during tests.
                    try:
                        ro_session.rollback()
                    finally:
                        ro_session.close()
        return response

    return db_tween


class Database(object):
    """A class representing an active database."""

    def __init__(self, uri):
        """
        :param uri: A database connection string.
        """
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


class HookedSession(Session):
    """A custom database session providing a post commit hook."""

    def __init__(self, *args, **kw):
        # disable automatic docstring
        return super(HookedSession, self).__init__(*args, **kw)

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
        """Use this active session to check the database connectivity."""
        try:
            self.execute(select([func.now()])).first()
        except exc.OperationalError:
            return False
        return True


@event.listens_for(Pool, 'checkin')
def clear_result_on_pool_checkin(conn, conn_record):
    """
    PyMySQL Connection objects hold a reference to their most recent
    result object, which can cause large datasets to remain in memory.
    Explicitly clear it when returning a connection to the pool.
    """
    if conn and conn._result:
        conn._result = None


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
