#!/bin/bash

# Drop and recreate the db
python ichnaea/scripts/db.py drop
python ichnaea/scripts/db.py create
