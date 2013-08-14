#!/bin/bash
PYRAMID_RELOAD_TEMPLATES=1 bin/gunicorn -b 127.0.0.1:7001 -w 1 -t 600 ichnaea:application
