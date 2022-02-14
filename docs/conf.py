# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
from os import path

import gino

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = "GINO"
copyright = "2017-present, Fantix King"
author = "Fantix King <fantix.king@gmail.com>"

# The full version, including alpha/beta/rc tags

release = gino.__version__

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinxcontrib.apidoc",
    "sphinx.ext.intersphinx",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "python-gino"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
html_css_files = ["gino.css"]
# html_logo = "images/logo.png"

# sphinxcontrib.apidoc
apidoc_module_dir = "../src"
apidoc_output_dir = "reference/api"
apidoc_separate_modules = True
apidoc_toc_file = False

# sphinx.ext.intersphinx
intersphinx_mapping = {
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/latest/", None),
    "asyncpg": ("https://magicstack.github.io/asyncpg/current/", None),
    "python": ("https://docs.python.org/3", None),
}

locale_dirs = ["locale/"]  # path is example but recommended.
gettext_compact = False  # optional.
master_doc = "index"


def setup(app):
    app.add_html_theme(
        "python-gino", path.abspath(path.join(path.dirname(__file__), "theme"))
    )
