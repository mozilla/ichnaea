HERE = $(shell pwd)
BIN = $(HERE)/bin
BUILD_DIRS = bin build dist include lib lib64 libmaxminddb man node_modules share
TRAVIS ?= false

MAXMINDDB_VERSION = 1.1.1
MYSQL_DB = location
MYSQL_TEST_DB = test_location

ifeq ($(TRAVIS), true)
	MYSQL_USER ?= travis
	MYSQL_PWD ?=
	SQLURI ?= mysql+pymysql://$(MYSQL_USER)@localhost/$(MYSQL_TEST_DB)

	PYTHON = python
	PIP = pip
	NOSE = nosetests
else
	MYSQL_USER ?= root
	MYSQL_PWD ?= mysql
	SQLURI ?= mysql+pymysql://$(MYSQL_USER):$(MYSQL_PWD)@localhost/$(MYSQL_TEST_DB)

	PYTHON = $(BIN)/python
	PIP = $(BIN)/pip
	NOSE = $(BIN)/nosetests
endif

PIP_WHEEL_DIR ?= $(HERE)/wheelhouse
INSTALL = $(PIP) install --no-deps -f $(PIP_WHEEL_DIR)
WHEEL = $(PIP) wheel --no-deps -w $(PIP_WHEEL_DIR)


.PHONY: all js mysql init_db css js_map js test clean shell docs \
	build wheel release release_install release_compile

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
ifeq ($(TRAVIS), true)
	virtualenv .
else
	virtualenv-2.6 .
endif
	bin/pip install -U pip

libmaxminddb/bootstrap:
	git clone --recursive git://github.com/maxmind/libmaxminddb
	cd libmaxminddb; git checkout 1.0.4
	cd libmaxminddb; git submodule update --init --recursive

libmaxminddb/Makefile:
	cd libmaxminddb; ./bootstrap
	cd libmaxminddb; ./configure --prefix=$(HERE)

lib/libmaxminddb.0.dylib: libmaxminddb/bootstrap libmaxminddb/Makefile
	cd libmaxminddb; make
	cd libmaxminddb; make install

install_vaurien_deps:
	$(INSTALL) -r requirements/vaurien.txt
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

build: $(PYTHON) mysql lib/libmaxminddb.0.dylib
	CFLAGS=-I$(HERE)/include LDFLAGS=-L$(HERE)/lib \
		$(INSTALL) maxminddb==$(MAXMINDDB_VERSION)
	$(INSTALL) -r requirements/prod-c.txt
	$(INSTALL) -r requirements/prod.txt
	$(INSTALL) -r requirements/test-c.txt
	$(INSTALL) -r requirements/test.txt
	$(PYTHON) setup.py develop

wheel:
	$(INSTALL) wheel
	$(PYTHON) compile_wheels.py -c "$(WHEEL)" -w $(PIP_WHEEL_DIR) \
		-f requirements/prod-c.txt -f requirements/test-c.txt

init_db:
	$(BIN)/location_initdb --initdb

css: node_modules
	$(HERE)/node_modules/.bin/cleancss -d \
	-o $(HERE)/ichnaea/content/static/css/base-combined.css \
	$(HERE)/ichnaea/content/static/css/base.css
	$(HERE)/node_modules/.bin/cleancss -d \
	-o $(HERE)/ichnaea/content/static/css/stat-countries-combined.css \
	$(HERE)/ichnaea/content/static/css/jquery.datatables.min.css
	$(HERE)/node_modules/.bin/cleancss -d \
	-o $(HERE)/ichnaea/content/static/css/map-combined.css \
	$(HERE)/ichnaea/content/static/css/mapbox-1.6.4.min.css

js_map:
	$(HERE)/node_modules/.bin/uglifyjs \
	$(HERE)/ichnaea/content/static/js/mapbox-1.6.4.min.js \
	$(HERE)/ichnaea/content/static/js/leaflet-hash-0.2.1.js \
	$(HERE)/ichnaea/content/static/js/leaflet-locatecontrol-0.24.0.js \
		$(HERE)/ichnaea/content/static/js/map.js \
	-o $(HERE)/ichnaea/content/static/js/map-combined.js \
	-m -c --stats

js: node_modules js_map
	$(HERE)/node_modules/.bin/uglifyjs \
	$(HERE)/ichnaea/content/static/js/privacy.js \
	-o $(HERE)/ichnaea/content/static/js/privacy-combined.js \
	-c --stats
	$(HERE)/node_modules/.bin/uglifyjs \
	$(HERE)/ichnaea/content/static/js/jquery.flot-0.8.3.js \
	$(HERE)/ichnaea/content/static/js/jquery.flot.time-0.8.3.js \
	$(HERE)/ichnaea/content/static/js/stat.js \
	-o $(HERE)/ichnaea/content/static/js/stat-combined.js \
	-c --stats
	$(HERE)/node_modules/.bin/uglifyjs \
	$(HERE)/ichnaea/content/static/js/jquery.datatables.min.js \
	$(HERE)/ichnaea/content/static/js/datatables.fixedheader.min.js \
	$(HERE)/ichnaea/content/static/js/stat-countries.js \
	-o $(HERE)/ichnaea/content/static/js/stat-countries-combined.js \
	-c --stats
	$(HERE)/node_modules/.bin/uglifyjs \
	$(HERE)/ichnaea/content/static/js/ga.js \
	$(HERE)/ichnaea/content/static/js/jquery-1.11.1.js \
	-o $(HERE)/ichnaea/content/static/js/base-combined.js \
	-m -c --stats

clean:
	rm -rf $(BUILD_DIRS)
	rm -f $(HERE)/.coverage
	rm -f $(HERE)/*.log
	rm -rf $(HERE)/ichnaea.egg-info

test: mysql
ifeq ($(TRAVIS), false)
	$(BIN)/coverage erase
endif
	SQLURI=$(SQLURI) CELERY_ALWAYS_EAGER=true \
	LD_LIBRARY_PATH=$$LD_LIBRARY_PATH:$(HERE)/lib \
	$(NOSE) -s -d -v --with-coverage --cover-package ichnaea ichnaea

$(BIN)/sphinx-build:
	$(INSTALL) -r requirements/docs.txt

shell:
	SQLURI=$(SQLURI) $(PYTHON) scripts/start_ipython.py

docs: $(BIN)/sphinx-build
	git submodule update --recursive --init
	cd docs; make html

release_install:
	$(INSTALL) -r requirements/prod-c.txt
	$(INSTALL) -r requirements/prod.txt
	$(PYTHON) setup.py install

release_compile:
	$(PYTHON) compile.py

release: release_install release_compile
