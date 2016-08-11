#!/bin/sh

exec /app/bin/gunicorn -b :${PORT:-8000} -c python:ichnaea.webapp.settings ichnaea.webapp.app:wsgi_app
