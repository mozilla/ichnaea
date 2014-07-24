HERE = $(shell pwd)
BIN = $(HERE)/bin
PYTHON = $(BIN)/python
PIP = $(BIN)/pip
INSTALL = $(PIP) install --no-deps --allow-external=argparse
NOSE = $(BIN)/nosetests

TRAVIS ?= false

BUILD_DIRS = bin build dist include lib lib64 man node_modules share

MYSQL_DB = location
MYSQL_TEST_DB = test_location
ifeq ($(TRAVIS), true)
	MYSQL_USER ?= travis
	MYSQL_PWD ?=
	SQLURI ?= mysql+pymysql://$(MYSQL_USER)@localhost/$(MYSQL_TEST_DB)

	PYTHON = python
	PIP = pip
	INSTALL = $(PIP) install --no-deps --allow-external=argparse
	NOSE = nosetests
else
	MYSQL_USER ?= root
	MYSQL_PWD ?= mysql
	SQLURI ?= mysql+pymysql://$(MYSQL_USER):$(MYSQL_PWD)@localhost/$(MYSQL_TEST_DB)
endif

.PHONY: all js mysql init_db css js_map js test clean shell docs release

all: build init_db

mysql:
ifeq ($(TRAVIS), true)
	mysql -u$(MYSQL_USER) -h localhost -e \
		"create database $(MYSQL_TEST_DB)" || echo
else
	mysql -u$(MYSQL_USER) -p$(MYSQL_PWD) -h localhost -e \
		"create database $(MYSQL_DB)" || echo
	mysql -u$(MYSQL_USER) -p$(MYSQL_PWD) -h localhost -e \
		"create database $(MYSQL_TEST_DB)" || echo
endif

node_modules:
	npm install $(HERE)

$(PYTHON):
	virtualenv .
	bin/pip install -U pip

install_vaurien_deps:
	$(INSTALL) -r requirements/vaurien.txt
	$(INSTALL) -r requirements/prod.txt
	$(INSTALL) -r requirements/test.txt
	$(INSTALL) -r requirements/loads.txt

# Start vaurien for MySQL with REST API enabled on port 8080
mysql_vaurien:
	vaurien --http --http-port 8080 --proxy 0.0.0.0:4404  --backend 0.0.0.0:3306 --protocol mysql
	#
# Start vaurien for redis with REST API enabled on port 8090
redis_vaurien:
	vaurien --http --http-port 8090 --proxy 0.0.0.0:9379 --backend 0.0.0.0:6379 --protocol redis

start_ichnaea:
	ICHNAEA_CFG=integration_tests/ichnaea.ini ./run_server.sh

automate_vaurien:
	SQLURI=$(SQLURI) nosetests -sv integration_tests/test_integration.py

build: $(PYTHON) mysql
	$(INSTALL) -r requirements/prod.txt
	$(INSTALL) -r requirements/test.txt
	$(PYTHON) setup.py develop

init_db:
	$(BIN)/location_initdb --initdb

css: node_modules
	$(HERE)/node_modules/.bin/cleancss -d \
	-o $(HERE)/ichnaea/content/static/css/base-combined.css \
	$(HERE)/ichnaea/content/static/css/base.css
	$(HERE)/node_modules/.bin/cleancss -d \
	-o $(HERE)/ichnaea/content/static/css/stat-combined.css \
	$(HERE)/ichnaea/content/static/css/rickshaw-1.5.0.min.css

js_map:
	$(HERE)/node_modules/.bin/uglifyjs \
	$(HERE)/ichnaea/content/static/js/mapbox-1.6.4.min.js \
	$(HERE)/ichnaea/content/static/js/leaflet-hash-0.2.1.js \
	$(HERE)/ichnaea/content/static/js/map.js \
	-o $(HERE)/ichnaea/content/static/js/map-combined.js \
	-m -c --stats

js: node_modules js_map
	$(HERE)/node_modules/.bin/uglifyjs \
	$(HERE)/ichnaea/content/static/js/d3-3.3.11.min.js \
	$(HERE)/ichnaea/content/static/js/rickshaw-1.5.0.min.js \
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
	SQLURI=$(SQLURI) CELERY_ALWAYS_EAGER=true \
	$(NOSE) -s -d -v --with-coverage --cover-package ichnaea ichnaea

bin/sphinx-build:
	$(INSTALL) -r requirements/docs.txt

shell:
	SQLURI=$(SQLURI) $(PYTHON) scripts/start_ipython.py

docs:  bin/sphinx-build
	git submodule update --recursive --init
	cd docs; make html

release:
	$(INSTALL) -r requirements/prod.txt
	$(PYTHON) setup.py install
