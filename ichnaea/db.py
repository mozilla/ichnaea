from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.expression import Insert
from sqlalchemy.orm import sessionmaker

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

def db_master_session(request):
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
        response = handler(request)
        master_session = getattr(request, '_db_master_session', None)
        if master_session is not None:
            # only deal with requests with a session
            if response.status.startswith(('4', '5')):  # pragma: no cover
                # never commit on error
                master_session.rollback()
            master_session.close()
        slave_session = getattr(request, '_db_slave_session', None)
        if slave_session is not None:
            # always rollback/close the `read-only` slave sessions
            try:
                slave_session.rollback()
            finally:
                slave_session.close()
        return response

    return db_tween


class Database(object):

    def __init__(self, uri, socket=None, echo=False,
                 isolation_level='REPEATABLE READ'):
        options = {
            'pool_recycle': 3600,
            'pool_size': 10,
            'pool_timeout': 10,
            'echo': echo,
            # READ COMMITTED
            'isolation_level': isolation_level,
        }
        options['connect_args'] = {'charset': 'utf8'}
        if socket:  # pragma: no cover
            options['connect_args'] = {'unix_socket': socket}
        options['execution_options'] = {'autocommit': False}
        self.engine = create_engine(uri, **options)
        self.session_factory = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False)

    def session(self):
        return self.session_factory()
