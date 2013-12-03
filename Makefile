HERE = $(shell pwd)
BIN = $(HERE)/bin
PYTHON = $(BIN)/python

INSTALL = $(BIN)/pip install --no-deps
VTENV_OPTS ?= --distribute
TRAVIS ?= false

BUILD_DIRS = bin build dist include lib lib64 man node_modules share

MYSQL_TEST_DB = test_location
ifeq ($(TRAVIS), true)
	MYSQL_USER ?= travis
	MYSQL_PWD ?=
	SQLURI ?= mysql+pymysql://$(MYSQL_USER)@localhost/$(MYSQL_TEST_DB)
	SQLSOCKET ?=
else
	MYSQL_USER ?= root
	MYSQL_PWD ?= mysql
	SQLURI ?= mysql+pymysql://$(MYSQL_USER):$(MYSQL_PWD)@localhost/$(MYSQL_TEST_DB)
	SQLSOCKET ?= /opt/local/var/run/mysql56/mysqld.sock
endif

.PHONY: all js test docs mysql

all: build

mysql:
ifeq ($(TRAVIS), true)
	mysql -u$(MYSQL_USER) -h localhost -e "create database $(MYSQL_TEST_DB)"
else
	mysql -u$(MYSQL_USER) -p$(MYSQL_PWD) -h localhost -e \
		"create database $(MYSQL_TEST_DB)" || echo
endif

node_modules:
	npm install $(HERE)

$(PYTHON):
	virtualenv $(VTENV_OPTS) .

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
	$(HERE)/ichnaea/content/static/js/mapbox-1.5.0.min.js \
	$(HERE)/ichnaea/content/static/js/map_world.js \
	$(HERE)/ichnaea/content/static/js/leaflet.markercluster-0.3.0-20131113.js \
	$(HERE)/ichnaea/content/static/js/csv2geojson-3.6.0.js \
	-o $(HERE)/ichnaea/content/static/js/map_world-combined.js \
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
	SQLURI=$(SQLURI) SQLSOCKET=$(SQLSOCKET) CELERY_ALWAYS_EAGER=true \
	$(BIN)/nosetests -s -d -v --with-coverage --cover-package ichnaea ichnaea

bin/sphinx-build:
	bin/pip install Sphinx

docs:  bin/sphinx-build
	cd docs; make html
