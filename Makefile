HERE = $(shell pwd)
BIN = $(HERE)/bin
BUILD_DIRS = bin build dist include lib lib64 libmaxminddb man node_modules share
TESTS ?= ichnaea
TRAVIS ?= false

MAXMINDDB_VERSION = 1.2.0
MYSQL_DB = location
MYSQL_TEST_DB = test_location

ifeq ($(TRAVIS), true)
	MYSQL_USER ?= travis
	MYSQL_PWD ?=
	SQLURI ?= mysql+pymysql://$(MYSQL_USER)@localhost/$(MYSQL_TEST_DB)

	PYTHON = python
	PIP = pip
	NOSE = nosetests
	SPHINXBUILD = sphinx-build
else
	MYSQL_USER ?= root
	MYSQL_PWD ?= mysql
	SQLURI ?= mysql+pymysql://$(MYSQL_USER):$(MYSQL_PWD)@localhost/$(MYSQL_TEST_DB)

	PYTHON = $(BIN)/python
	PIP = $(BIN)/pip
	NOSE = $(BIN)/nosetests
	SPHINXBUILD = $(BIN)/sphinx-build
endif

TRAVIS_PYTHON_VERSION ?= $(shell $(PYTHON) -c "import sys; print('.'.join([str(s) for s in sys.version_info][:2]))")
PYTHON_2 = yes
ifeq ($(findstring 3.,$(TRAVIS_PYTHON_VERSION)), 3.)
	PYTHON_2 = no
endif

ifeq ($(TESTS), ichnaea)
	TEST_ARG = ichnaea --with-coverage --cover-package ichnaea \
	--cover-branches --cover-erase
else
	TEST_ARG = --tests=$(TESTS)
endif

PIP_WHEEL_DIR ?= $(HERE)/wheelhouse
INSTALL = $(PIP) install --no-deps -f file://$(PIP_WHEEL_DIR)
WHEEL = $(PIP) wheel --no-deps -w $(PIP_WHEEL_DIR)

BOWER_ROOT = $(HERE)/bower_components
STATIC_ROOT = $(HERE)/ichnaea/content/static
CSS_ROOT = $(STATIC_ROOT)/css
FONT_ROOT = $(STATIC_ROOT)/fonts
IMG_ROOT = $(STATIC_ROOT)/images
JS_ROOT = $(STATIC_ROOT)/js

NODE_BIN = $(HERE)/node_modules/.bin
BOWER = $(NODE_BIN)/bower
BROWSERIFY = $(NODE_BIN)/browserify
CLEANCSS = cd $(CSS_ROOT) && $(NODE_BIN)/cleancss -d --source-map
UGLIFYJS = cd $(JS_ROOT) && $(NODE_BIN)/uglifyjs


.PHONY: all bower js mysql init_db css js test clean shell docs \
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

build: $(PYTHON) mysql lib/libmaxminddb.0.dylib
	CFLAGS=-I$(HERE)/include LDFLAGS=-L$(HERE)/lib \
		$(INSTALL) maxminddb==$(MAXMINDDB_VERSION)
	$(INSTALL) -r requirements/prod-c.txt
	$(INSTALL) -r requirements/prod.txt
	$(INSTALL) -r requirements/test-c.txt
	$(INSTALL) -r requirements/test.txt
ifeq ($(PYTHON_2),no)
	$(INSTALL) -r requirements/override-3.txt
endif
	$(PYTHON) setup.py develop

release_install:
	$(INSTALL) -r requirements/prod-c.txt
	$(INSTALL) -r requirements/prod.txt
	$(PYTHON) setup.py install

release_compile:
	$(PYTHON) compile.py

release: release_install release_compile

wheel:
	$(INSTALL) wheel
	$(PYTHON) compile_wheels.py -c "$(WHEEL)" -w $(PIP_WHEEL_DIR) \
		-f requirements/prod-c.txt -f requirements/test-c.txt

init_db:
	$(BIN)/location_initdb --initdb

node_modules:
	npm install -d $(HERE)
	npm dedupe
	npm shrinkwrap --dev

bower: node_modules
	$(BOWER) install

css: bower
	cp $(BOWER_ROOT)/bedrock/media/fonts/OpenSans* $(FONT_ROOT)/
	cp $(BOWER_ROOT)/bedrock/media/img/sandstone/bg-stone.png $(IMG_ROOT)/
	cp $(BOWER_ROOT)/bedrock/media/img/sandstone/footer-mozilla.png \
		$(IMG_ROOT)/mozilla-logo.png
	cp $(BOWER_ROOT)/bedrock/media/img/sandstone/footer-mozilla-high-res.png \
		$(IMG_ROOT)/mozilla-logo@2x.png
	cp $(BOWER_ROOT)/bedrock/media/img/sandstone/menu-current.png $(IMG_ROOT)/
	$(CLEANCSS) -o bundle-base.css base.css

	cp $(BOWER_ROOT)/datatables/media/css/jquery.dataTables.css $(CSS_ROOT)
	$(CLEANCSS) -o bundle-stat-regions.css jquery.dataTables.css

	cp $(BOWER_ROOT)/fontawesome/fonts/* $(FONT_ROOT)/
	cp $(BOWER_ROOT)/fontawesome/css/font-awesome.css $(CSS_ROOT)
	cp $(BOWER_ROOT)/mapbox.js/mapbox.uncompressed.css $(CSS_ROOT)
	mkdir -p $(CSS_ROOT)/images/
	cp -R $(BOWER_ROOT)/mapbox.js/images/*.png $(CSS_ROOT)/images/
	$(CLEANCSS) -o bundle-map.css font-awesome.css mapbox.uncompressed.css

js: bower
	$(UGLIFYJS) \
		privacy.js \
		-o bundle-privacy.js -c --stats \
		--source-map bundle-privacy.js.map

	cp $(BOWER_ROOT)/jquery/dist/jquery.js $(JS_ROOT)
	$(UGLIFYJS) \
		ga.js \
		jquery.js \
		-o bundle-base.js -c --stats \
		--source-map bundle-base.js.map

	cp $(BOWER_ROOT)/datatables/media/js/jquery.dataTables.js $(JS_ROOT)
	cp $(BOWER_ROOT)/datatables-fixedheader/js/dataTables.fixedHeader.js $(JS_ROOT)
	$(UGLIFYJS) \
		jquery.dataTables.js \
		dataTables.fixedHeader.js \
		stat-regions.js \
		-o bundle-stat-regions.js -c --stats \
		--source-map bundle-stat-regions.js.map

	cp $(BOWER_ROOT)/flot/jquery.flot.js $(JS_ROOT)
	cp $(BOWER_ROOT)/flot/jquery.flot.time.js $(JS_ROOT)
	$(UGLIFYJS) \
		jquery.flot.js \
		jquery.flot.time.js \
		stat.js \
		-o bundle-stat.js -c --stats \
		--source-map bundle-stat.js.map

	cp $(BOWER_ROOT)/mapbox.js/mapbox.uncompressed.js $(JS_ROOT)
	cp $(BOWER_ROOT)/leaflet-hash/leaflet-hash.js $(JS_ROOT)
	cp $(BOWER_ROOT)/leaflet.locatecontrol/src/L.Control.Locate.js $(JS_ROOT)
	$(UGLIFYJS) \
		mapbox.uncompressed.js \
		leaflet-hash.js \
		L.Control.Locate.js \
		map.js \
		-o bundle-map.js -c --stats \
		--source-map bundle-map.js.map

clean:
	rm -rf $(BUILD_DIRS)
	rm -f $(HERE)/.coverage
	rm -f $(HERE)/*.log
	rm -rf $(HERE)/ichnaea.egg-info

test: mysql
	SQLURI=$(SQLURI) CELERY_ALWAYS_EAGER=true \
	LD_LIBRARY_PATH=$$LD_LIBRARY_PATH:$(HERE)/lib \
	$(NOSE) -s -d -v $(TEST_ARG)

$(BIN)/sphinx-build:
	$(INSTALL) -r requirements/docs.txt

docs: $(BIN)/sphinx-build
	git submodule update --recursive --init
	cd docs; SPHINXBUILD=$(SPHINXBUILD) make html
