#!/bin/sh

# Runs the webapp in gunicorn.

PORT=${PORT:-8000}
echo "Running webserver on http://localhost:${PORT} ..."

gunicorn \
	--pythonpath /app \
	--error-logfile=- \
	--access-logfile=- \
	--log-file=- \
	--config=python:ichnaea.webapp.settings \
	--bind 0.0.0.0:"${PORT}" \
	ichnaea.webapp.app:wsgi_app
