#!/bin/sh

celery -A ichnaea.taskapp.app:celery_app worker
