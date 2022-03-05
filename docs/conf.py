# -*- coding: utf-8 -*-

import os
import sys
from unittest import mock


# Add repository root so we can import ichnaea things
REPO_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(REPO_DIR)


# Fake the shapely module so things will import
sys.modules["shapely"] = mock.MagicMock()


project = "Ichnaea"
copyright = "2013-2022, Mozilla"

# The short X.Y version.
version = "2.3"
# The full version, including alpha/beta/rc tags.
release = "2.3"

autoclass_content = "class"
exclude_patterns = ["_build", ".DS_Store", "Thumbs.db"]
html_static_path = []
modindex_common_prefix = ["ichnaea."]
pygments_style = "sphinx"
source_suffix = ".rst"
templates_path = ["_templates"]

# Use default theme if we are in ReadTheDocs
on_rtd = os.environ.get("READTHEDOCS") == "True"
if on_rtd:
    html_theme = "default"
else:
    import sphinx_rtd_theme

    html_theme = "sphinx_rtd_theme"
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

extensions = [
    "sphinx.ext.linkcode",
    "everett.sphinxext",
]


def linkcode_resolve(domain, info):
    if domain != "py":
        return None
    if not info["module"]:
        return None
    filename = info["module"].replace(".", "/")
    return "https://github.com/mozilla/ichnaea/tree/main/%s.py" % filename
