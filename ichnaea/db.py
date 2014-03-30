from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.expression import Insert
from sqlalchemy.orm import sessionmaker

_VolatileModel = declarative_base()
_ArchivalModel = declarative_base()


@compiles(Insert)
def on_duplicate(insert, compiler, **kw):
    s = compiler.visit_insert(insert, **kw)
    if 'on_duplicate' in insert.kwargs:
        return s + " ON DUPLICATE KEY UPDATE " + insert.kwargs['on_duplicate']
    return s


# the request db_sessions and db_tween_factory are inspired by pyramid_tm
# to provide lazy session creation, session closure and automatic
# rollback in case of errors

def archival_db_session(request):
    session = getattr(request, '_archival_db_session', None)
    if session is None:
        db = request.registry.archival_db
        request._archival_db_session = session = db.session()
    return session


def volatile_db_session(request):
    session = getattr(request, '_volatile_db_session', None)
    if session is None:
        db = request.registry.volatile_db
        request._volatile_db_session = session = db.session()
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
        archival_session = getattr(request, '_archival_db_session', None)
        if archival_session is not None:
            # only deal with requests with a session
            if response.status.startswith(('4', '5')):  # pragma: no cover
                # never commit on error
                archival_session.rollback()
            archival_session.close()
        volatile_session = getattr(request, '_volatile_db_session', None)
        if volatile_session is not None:
            # always rollback/close the `read-only` volatile sessions
            try:
                volatile_session.rollback()
            finally:
                volatile_session.close()
        return response

    return db_tween


class Database(object):

    def __init__(self, uri, model_base,
                 socket=None, create=True, echo=False,
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

        # create tables
        if create:
            with self.engine.connect() as conn:
                trans = conn.begin()
                model_base.metadata.create_all(self.engine)
                trans.commit()

    def session(self):
        return self.session_factory()
