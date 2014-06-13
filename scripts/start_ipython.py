#!/usr/bin/env python

from IPython.config.loader import Config
from IPython.terminal.embed import InteractiveShellEmbed
from ichnaea.tests.base import _make_db
import os
from os.path import split, abspath
import sys

thisfile = abspath(__file__)
ichnaea_root = split(split(thisfile)[0])[0]
sys.path.append(ichnaea_root)

SQLURI = os.environ.get('SQLURI')
db = _make_db(SQLURI)
session = db.session()

ipshell = InteractiveShellEmbed(config=Config(),
                                banner1 = 'Dropping into IPython',
                                exit_msg = 'Leaving Interpreter, back to program.')
ipshell()
