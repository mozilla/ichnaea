# -*- coding: utf-8 -*-

import os
import sphinx_rtd_theme
import sys
from unittest import mock


# Add repository root so we can import ichnaea things
REPO_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(REPO_DIR)


# Fake the shapely module so things will import
sys.modules['shapely'] = mock.MagicMock()


project = 'Ichnaea'
copyright = '2013-2019, Mozilla'

# The short X.Y version.
version = '2.0'
# The full version, including alpha/beta/rc tags.
release = '2.0'

autoclass_content = 'class'
exclude_patterns = ['build/html/README.rst', '.DS_Store', 'Thumbs.db']
html_static_path = []
html_theme = 'sphinx_rtd_theme'
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
master_doc = 'index'
modindex_common_prefix = ['ichnaea.']
pygments_style = 'sphinx'
source_suffix = '.rst'
templates_path = ['_templates']

extensions = [
    'sphinx.ext.linkcode',
    'everett.sphinxext',
]


def linkcode_resolve(domain, info):
    if domain != 'py':
        return None
    if not info['module']:
        return None
    filename = info['module'].replace('.', '/')
    return "https://github.com/mozilla/ichnaea/tree/master/%s.py" % filename
