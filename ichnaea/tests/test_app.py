from ichnaea.db import _VolatileModel, _ArchivalModel
from ichnaea.tests.base import (
    _make_app,
    _make_db,
    DBTestCase,
    SQLURI_ARCHIVAL,
    SQLURI_VOLATILE,
    SQLSOCKET_ARCHIVAL,
    SQLSOCKET_VOLATILE,
)


class TestApp(DBTestCase):

    def test_db_hooks(self):
        settings = {
            'archival_db_url': SQLURI_ARCHIVAL,
            'archival_db_socket': SQLSOCKET_ARCHIVAL,
            'volatile_db_url': SQLURI_VOLATILE,
            'volatile_db_socket': SQLSOCKET_VOLATILE,
            '_heka_client': self.heka_client,
        }
        app = _make_app(**settings)
        self.archival_db = app.app.registry.archival_db
        self.volatile_db = app.app.registry.volatile_db
        self.setup_session()
        app.get('/stats_unique_cell.json', status=200)

    def test_db_config(self):
        self.archival_db = _make_db(_ArchivalModel,
                                    SQLURI_ARCHIVAL, SQLSOCKET_ARCHIVAL)
        self.volatile_db = _make_db(_VolatileModel,
                                    SQLURI_VOLATILE, SQLSOCKET_VOLATILE)
        self.setup_session()
        app = _make_app(_archival_db=self.archival_db,
                        _volatile_db=self.volatile_db,
                        _heka_client=self.heka_client)
        app.get('/stats_unique_cell.json', status=200)
