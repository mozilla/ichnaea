# -*- coding: utf-8 -*-
#
# Ichnaea documentation build configuration file, created by
# sphinx-quickstart on Fri Apr 19 11:29:25 2013.

import os

# on_rtd is whether we are on readthedocs.org
on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
    'sphinx.ext.linkcode',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'Ichnaea'
copyright = u'2013-2015, Mozilla'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '1.3'
# The full version, including alpha/beta/rc tags.
release = '1.3'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = []

intersphinx_mapping = {
    'celery': ('https://celery.readthedocs.org/en/latest/', None),
    'geoip2': ('https://geoip2.readthedocs.org/en/latest/', None),
    'gunicorn': ('http://docs.gunicorn.org/en/latest/', None),
    'kombu': ('https://kombu.readthedocs.org/en/latest/', None),
    'maxminddb': ('https://maxminddb.readthedocs.org/en/latest/', None),
    'pyramid': ('https://pyramid.readthedocs.org/en/latest/', None),
    'python': ('https://docs.python.org/2.7', None),
    'raven': ('https://raven.readthedocs.org/en/latest/', None),
    'requests': ('https://requests.readthedocs.org/en/latest/', None),
}

autoclass_content = 'both'

modindex_common_prefix = ['ichnaea.']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'


if not on_rtd:  # only import and set the theme if we're building docs locally
    import sphinx_rtd_theme

    html_theme = 'sphinx_rtd_theme'
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = []


def linkcode_resolve(domain, info):
    if domain != 'py':
        return None
    if not info['module']:
        return None
    filename = info['module'].replace('.', '/')
    return "https://github.com/mozilla/ichnaea/tree/master/%s.py" % filename


# Output file base name for HTML help builder.
htmlhelp_basename = 'Ichnaeadoc'

latex_elements = {}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual])
latex_documents = [
    ('index', 'Ichnaea.tex', u'Ichnaea Documentation',
     u'Mozilla', 'manual'),
]

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'ichnaea', u'Ichnaea Documentation',
     [u'Mozilla'], 1)
]

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    ('index', 'Ichnaea', u'Ichnaea Documentation',
     u'Mozilla', 'Ichnaea', '', 'Miscellaneous'),
]
