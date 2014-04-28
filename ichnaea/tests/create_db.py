from ichnaea.tests.base import (
    SQLURI,
    SQLSOCKET,
)
from ichnaea.tests.base import _make_db


if __name__ == '__main__':
    _make_db(SQLURI, SQLSOCKET)
