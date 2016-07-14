HERE = $(shell pwd)
BIN = $(HERE)/bin
BUILD_DIRS = .tox bin build datamaps dist include \
	lib lib64 libmaxminddb man pngquant share
TESTS ?= ichnaea
TRAVIS ?= false

TOXENVDIR ?= $(HERE)/.tox/tmp
TOXINIDIR ?= $(HERE)
ICHNAEA_CFG ?= $(TOXINIDIR)/ichnaea/tests/data/test.ini

MAXMINDDB_VERSION = 1.2.1
MYSQL_DB = location
MYSQL_TEST_DB = test_location

DOCKER_BIN ?= docker
DOCKER_COMPOSE_BIN ?= docker-compose

ifeq ($(TRAVIS), true)
	MYSQL_USER ?= travis
	MYSQL_PWD ?=
	MYSQL_HOST ?= localhost
	MYSQL_PORT ?= 3306
	SQLURI ?= mysql+pymysql://$(MYSQL_USER)@$(MYSQL_HOST)/$(MYSQL_TEST_DB)

	REDIS_HOST ?= localhost
	REDIS_PORT ?= 6379
	REDIS_URI ?= redis://$(REDIS_HOST):$(REDIS_PORT)/1

	PYTHON = python
	PIP = pip
	PYTEST = py.test
	CYTHON = cython
	SPHINXBUILD = sphinx-build
else
	MYSQL_USER ?= root
	MYSQL_PWD ?= mysql
	MYSQL_HOST ?= localhost
	MYSQL_PORT ?= 33306
	SQLURI ?= mysql+pymysql://$(MYSQL_USER):$(MYSQL_PWD)@$(MYSQL_HOST):$(MYSQL_PORT)/$(MYSQL_TEST_DB)

	REDIS_HOST ?= localhost
	REDIS_PORT ?= 36379
	REDIS_URI ?= redis://$(REDIS_HOST):$(REDIS_PORT)/1

	PYTHON = $(BIN)/python
	PIP = $(BIN)/pip
	PYTEST = $(BIN)/py.test
	CYTHON = $(BIN)/cython
	SPHINXBUILD = $(BIN)/sphinx-build
endif

TRAVIS_PYTHON_VERSION ?= $(shell $(PYTHON) -c "import sys; print('.'.join([str(s) for s in sys.version_info][:2]))")
PYTHON_2 = yes
ifeq ($(findstring 3.,$(TRAVIS_PYTHON_VERSION)), 3.)
	PYTHON_2 = no
endif

ifeq ($(TESTS), ichnaea)
	TEST_ARG = --durations=10 --cov-config=.coveragerc --cov=ichnaea ichnaea
else
	TEST_ARG = $(TESTS)
endif

INSTALL = $(PIP) install --no-deps --disable-pip-version-check

STATIC_ROOT = $(HERE)/ichnaea/content/static
CSS_ROOT = $(STATIC_ROOT)/css
FONT_ROOT = $(STATIC_ROOT)/fonts
IMG_ROOT = $(STATIC_ROOT)/images
JS_ROOT = $(STATIC_ROOT)/js

NODE_BIN = $(DOCKER_BIN) run --rm -a STDIN -a STDOUT -i mozilla-ichnaea/node:latest
CLEANCSS = $(NODE_BIN) cleancss -d
UGLIFYJS = $(NODE_BIN) uglifyjs -c --stats


.PHONY: all js mysql pip init_db css js test clean shell docs \
	docker docker-mysql docker-node docker-redis \
	build build_dev build_req build_cython \
	build_datamaps build_maxmind build_pngquant \
	release release_install release_compile \
	tox_install tox_test pypi_release pypi_upload

all: build init_db

docker: docker-mysql docker-redis
ifneq ($(TRAVIS), true)
	cd $(TOXINIDIR); $(DOCKER_COMPOSE_BIN) up -d
endif

docker-mysql:
ifneq ($(TRAVIS), true)
	cd docker/mysql; $(DOCKER_BIN) build -t mozilla-ichnaea/mysql:latest .
endif

docker-redis:
ifneq ($(TRAVIS), true)
	cd docker/redis; $(DOCKER_BIN) build -t mozilla-ichnaea/redis:latest .
endif

docker-node:
ifneq ($(TRAVIS), true)
	cd docker/node; $(DOCKER_BIN) build -t mozilla-ichnaea/node:latest .
endif

MYSQL_RET ?= 1
mysql: docker
	# Wait to confirm that MySQL has started.
	@MYSQL_RET=$(MYSQL_RET); \
	while [ $${MYSQL_RET} -ne 0 ] ; do \
		echo "Trying MySQL..." ; \
	    nc -dz $(MYSQL_HOST) $(MYSQL_PORT) ; \
		MYSQL_RET=$$? ; \
	    sleep 0.5 ; \
	    done; \
	true

ifeq ($(TRAVIS), true)
	mysql -u$(MYSQL_USER) -h localhost -e \
		"CREATE DATABASE IF NOT EXISTS $(MYSQL_TEST_DB)" || echo
endif


$(PYTHON):
ifeq ($(TRAVIS), true)
	virtualenv .
else
	virtualenv --python=python2.6 .
endif

pip:
	bin/pip install --disable-pip-version-check -r requirements/build.txt

datamaps/merge:
	git clone --recursive git://github.com/ericfischer/datamaps
	cd datamaps; git checkout 76e620adabbedabd6866b23b30c145b53bae751e
	cd datamaps; make all

build_datamaps: datamaps/merge

$(TOXINIDIR)/libmaxminddb/bootstrap:
	git clone --recursive git://github.com/maxmind/libmaxminddb
	cd libmaxminddb; git checkout 1.1.1
	cd libmaxminddb; git submodule update --init --recursive

$(TOXINIDIR)/libmaxminddb/Makefile:
	cd libmaxminddb; ./bootstrap
	cd libmaxminddb; ./configure --prefix=$(HERE)

$(TOXINIDIR)/lib/libmaxminddb.0.dylib: \
		$(TOXINIDIR)/libmaxminddb/bootstrap $(TOXINIDIR)/libmaxminddb/Makefile
	cd libmaxminddb; make
	cd libmaxminddb; make install

build_maxmind: $(PYTHON) pip $(TOXINIDIR)/lib/libmaxminddb.0.dylib
	CFLAGS=-I$(TOXINIDIR)/include LDFLAGS=-L$(TOXINIDIR)/lib \
		$(INSTALL) --no-binary :all: maxminddb==$(MAXMINDDB_VERSION)

pngquant/pngquant:
	git clone --recursive git://github.com/pornel/pngquant
	cd pngquant; git checkout 2.5.2
	cd pngquant; ./configure
	cd pngquant; make all

build_pngquant: pngquant/pngquant

ichnaea/geocalc.c: ichnaea/geocalc.pyx
	$(CYTHON) ichnaea/geocalc.pyx

build_cython: ichnaea/geocalc.c
	$(PYTHON) setup.py build_ext --inplace

build_req: $(PYTHON) pip build_datamaps build_maxmind build_pngquant
	$(INSTALL) -r requirements/prod.txt
	$(INSTALL) -r requirements/dev.txt

build_dev: $(PYTHON) build_cython
	$(INSTALL) -e .

build: build_req build_dev mysql

release_install:
	$(PIP) install --no-deps -r requirements/build.txt
	$(INSTALL) -r requirements/prod.txt
	$(PYTHON) setup.py install

release_compile:
ifeq ($(PYTHON_2),yes)
	$(PYTHON) compile.py
endif

release: release_install release_compile

init_db: mysql
	$(BIN)/location_initdb --initdb

css: docker-node
	$(NODE_BIN) cat \
		bower_components/mozilla-tabzilla/css/tabzilla.css > \
		$(CSS_ROOT)/tabzilla.css

	mkdir -p $(CSS_ROOT)/../media/img/
	$(NODE_BIN) cat \
		bower_components/mozilla-tabzilla/media/img/tabzilla-static.png > \
		$(CSS_ROOT)/../media/img/tabzilla-static.png
	$(NODE_BIN) cat \
		bower_components/mozilla-tabzilla/media/img/tabzilla-static-high-res.png > \
		$(CSS_ROOT)/../media/img/tabzilla-static-high-res.png

	cd $(CSS_ROOT) && \
		cat tabzilla.css base.css | \
		$(CLEANCSS) > bundle-base.css

	$(NODE_BIN) cat \
		bower_components/datatables/media/css/jquery.dataTables.css > \
		$(CSS_ROOT)/jquery.dataTables.css
	cd $(CSS_ROOT) && \
		cat jquery.dataTables.css | \
		$(CLEANCSS) > bundle-stat-regions.css

	$(NODE_BIN) cat \
		bower_components/font-awesome/css/font-awesome.css > \
		$(CSS_ROOT)/font-awesome.css
	$(NODE_BIN) cat \
		bower_components/mapbox.js/mapbox.uncompressed.css > \
		$(CSS_ROOT)/mapbox.uncompressed.css
	cd $(CSS_ROOT) && \
		cat font-awesome.css mapbox.uncompressed.css | \
		$(CLEANCSS) > bundle-map.css

	mkdir -p $(CSS_ROOT)/images/
	cd $(CSS_ROOT)/images/ && \
		$(NODE_BIN) tar c -C bower_components/mapbox.js/images/ . | \
		tar x -
	rm -f $(CSS_ROOT)/images/render.sh
	cd $(FONT_ROOT) && \
		$(NODE_BIN) tar c -C bower_components/font-awesome/fonts/ . | \
		tar x -


js: docker-node
	cd $(JS_ROOT) && cat \
		privacy.js | \
		$(UGLIFYJS) > bundle-privacy.js

	$(NODE_BIN) cat \
		bower_components/jquery/dist/jquery.js > \
		$(JS_ROOT)/jquery.js
	cd $(JS_ROOT) && cat \
		ga.js \
		jquery.js | \
		$(UGLIFYJS) > bundle-base.js

	$(NODE_BIN) cat \
		bower_components/datatables/media/js/jquery.dataTables.js > \
		$(JS_ROOT)/jquery.dataTables.js
	cd $(JS_ROOT) && cat \
		jquery.dataTables.js \
		stat-regions.js | \
		$(UGLIFYJS) > bundle-stat-regions.js

	$(NODE_BIN) cat \
		bower_components/flot/jquery.flot.js > \
		$(JS_ROOT)/jquery.flot.js
	$(NODE_BIN) cat \
		bower_components/flot/jquery.flot.time.js > \
		$(JS_ROOT)/jquery.flot.time.js
	cd $(JS_ROOT) && cat \
		jquery.flot.js \
		jquery.flot.time.js \
		stat.js | \
		$(UGLIFYJS) > bundle-stat.js

	$(NODE_BIN) cat \
		bower_components/mapbox.js/mapbox.uncompressed.js > \
		$(JS_ROOT)/mapbox.uncompressed.js
	$(NODE_BIN) cat \
		bower_components/leaflet-hash/leaflet-hash.js > \
		$(JS_ROOT)/leaflet-hash.js
	$(NODE_BIN) cat \
		bower_components/leaflet.locatecontrol/src/L.Control.Locate.js > \
		$(JS_ROOT)/L.Control.Locate.js
	cd $(JS_ROOT) && cat \
		mapbox.uncompressed.js \
		leaflet-hash.js \
		L.Control.Locate.js \
		map.js | \
		$(UGLIFYJS) > bundle-map.js

clean:
	rm -rf $(BUILD_DIRS)
	rm -f $(HERE)/.coverage
	rm -f $(HERE)/*.log
	rm -rf $(HERE)/ichnaea.egg-info

test: mysql
	SQLURI=$(SQLURI) REDIS_URI=$(REDIS_URI) CELERY_ALWAYS_EAGER=true \
	ICHNAEA_CFG=$(ICHNAEA_CFG) LD_LIBRARY_PATH=$$LD_LIBRARY_PATH:$(HERE)/lib \
	$(PYTEST) $(TEST_ARG)

tox_install:
ifeq ($(wildcard $(TOXENVDIR)/.git/),)
	git init $(TOXENVDIR)
	cd $(TOXENVDIR); git remote add upstream $(TOXINIDIR) --no-tags
endif
	cd $(TOXENVDIR); git fetch upstream --force
	cd $(TOXENVDIR); git checkout upstream/master --force
	cd $(TOXENVDIR); git reset --hard
	rm -rf $(TOXENVDIR)/ichnaea
	cp -f $(TOXINIDIR)/lib/libmaxminddb* $(TOXENVDIR)/lib/
	cd $(TOXENVDIR); make build_req
	cd $(TOXENVDIR); make mysql

tox_test:
	make tox_install
	cd $(TOXENVDIR); bin/pip install -e /opt/mozilla/ichnaea/ --no-compile
	cd $(TOXENVDIR); PYTHONDONTWRITEBYTECODE=True make test

$(BIN)/sphinx-build:
	$(INSTALL) -r requirements/dev.txt

docs: $(BIN)/sphinx-build
	cd docs; SPHINXBUILD=$(SPHINXBUILD) make html

pypi_release:
	rm -rf $(HERE)/dist
	$(PYTHON) setup.py egg_info -RDb '' sdist --formats=zip
	gpg --detach-sign -a $(HERE)/dist/ichnaea*.zip

pypi_upload:
	twine upload $(HERE)/dist/*
