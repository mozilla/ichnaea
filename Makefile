HERE = $(shell pwd)
BIN = $(HERE)/bin
PYTHON = $(BIN)/python
PIP = $(BIN)/pip
INSTALL = $(PIP) install --no-deps --allow-external=argparse
NOSE = $(BIN)/nosetests

TRAVIS ?= false

BUILD_DIRS = bin build dist include lib lib64 man node_modules share

MYSQL_TEST_ARCHIVAL_DB = test_location_archival
MYSQL_TEST_VOLATILE_DB = test_location_volatile
ifeq ($(TRAVIS), true)
	MYSQL_USER ?= travis
	MYSQL_PWD ?=
	SQLURI_ARCHIVAL ?= mysql+pymysql://$(MYSQL_USER)@localhost/$(MYSQL_TEST_ARCHIVAL_DB)
	SQLURI_VOLATILE ?= mysql+pymysql://$(MYSQL_USER)@localhost/$(MYSQL_TEST_VOLATILE_DB)
	SQLSOCKET_ARCHIVAL ?=
	SQLSOCKET_VOLATILE ?=

	PYTHON = python
	PIP = pip
	INSTALL = $(PIP) install --no-deps --allow-external=argparse
	NOSE = nosetests
else
	MYSQL_USER ?= root
	MYSQL_PWD ?= mysql
	SQLURI_ARCHIVAL ?= mysql+pymysql://$(MYSQL_USER):$(MYSQL_PWD)@localhost/$(MYSQL_TEST_ARCHIVAL_DB)
	SQLURI_VOLATILE ?= mysql+pymysql://$(MYSQL_USER):$(MYSQL_PWD)@localhost/$(MYSQL_TEST_VOLATILE_DB)
	SQLSOCKET_ARCHIVAL ?= /opt/local/var/run/mysql56/mysqld.sock
	SQLSOCKET_VOLATILE ?= /opt/local/var/run/mysql56/mysqld.sock
endif

.PHONY: all js test docs mysql

all: build

mysql:
ifeq ($(TRAVIS), true)
	mysql -u$(MYSQL_USER) -h localhost -e "create database $(MYSQL_TEST_ARCHIVAL_DB)"
	mysql -u$(MYSQL_USER) -h localhost -e "create database $(MYSQL_TEST_VOLATILE_DB)"
else
	mysql -u$(MYSQL_USER) -p$(MYSQL_PWD) -h localhost -e \
		"create database $(MYSQL_TEST_ARCHIVAL_DB)" || echo
	mysql -u$(MYSQL_USER) -p$(MYSQL_PWD) -h localhost -e \
		"create database $(MYSQL_TEST_VOLATILE_DB)" || echo
endif

node_modules:
	npm install $(HERE)

$(PYTHON):
	virtualenv .
	bin/pip install -U pip

build: $(PYTHON)
	$(INSTALL) -r requirements/prod.txt
	$(INSTALL) -r requirements/test.txt
	$(PYTHON) setup.py develop
ifneq ($(TRAVIS), true)
	mysql -u$(MYSQL_USER) -p$(MYSQL_PWD) -h localhost -e \
		"create database location" || echo
endif

js: node_modules
	$(HERE)/node_modules/.bin/uglifyjs \
	$(HERE)/ichnaea/content/static/js/mapbox-1.5.2.min.js \
	$(HERE)/ichnaea/content/static/js/leaflet-hash-20140111.js \
	$(HERE)/ichnaea/content/static/js/map.js \
	-o $(HERE)/ichnaea/content/static/js/map-combined.js \
	-m -c --stats
	$(HERE)/node_modules/.bin/uglifyjs \
	$(HERE)/ichnaea/content/static/js/d3-3.3.11.min.js \
	$(HERE)/ichnaea/content/static/js/rickshaw-1.4.5.min.js \
	$(HERE)/ichnaea/content/static/js/stat.js \
	-o $(HERE)/ichnaea/content/static/js/stat-combined.js \
	-c --stats
	$(HERE)/node_modules/.bin/uglifyjs \
	$(HERE)/ichnaea/content/static/js/ga.js \
	$(HERE)/ichnaea/content/static/js/jquery-1.9.1.js \
	-o $(HERE)/ichnaea/content/static/js/base-combined.js \
	-m -c --stats

clean:
	rm -rf $(BUILD_DIRS)
	rm -f $(HERE)/.coverage
	rm -f $(HERE)/*.log
	rm -rf $(HERE)/ichnaea.egg-info

test: mysql
	SQLURI_ARCHIVAL=$(SQLURI_ARCHIVAL) \
	SQLURI_VOLATILE=$(SQLURI_VOLATILE) \
	SQLSOCKET_ARCHIVAL=$(SQLSOCKET_ARCHIVAL) \
	SQLSOCKET_VOLATILE=$(SQLSOCKET_VOLATILE) \
	CELERY_ALWAYS_EAGER=true \
	$(NOSE) -s -d -v --with-coverage --cover-package ichnaea ichnaea

bin/sphinx-build:
	$(INSTALL) Sphinx

docs:  bin/sphinx-build
	cd docs; make html
