#!/bin/bash
if [ -n "${VENV_BIN}" ]; then
    GUNICORN_BIN=${VENV_BIN}/gunicorn
else
    GUNICORN_BIN=bin/gunicorn
fi

ICHNAEA_CFG=location.ini PYRAMID_RELOAD_TEMPLATES=1 \
    DB_RW_URI=mysql+pymysql://root:mysql@localhost:33306/location \
    DB_RO_URI=mysql+pymysql://root:mysql@localhost:33306/location \
    GEOIP_PATH=ichnaea/tests/data/GeoIP2-City-Test.mmdb \
    REDIS_HOST=localhost REDIS_PORT=36379 \
    ${GUNICORN_BIN} \
    -b 127.0.0.1:7001 -w 1 -t 600 \
    -c python:ichnaea.webapp.settings ichnaea.webapp.app:wsgi_app
