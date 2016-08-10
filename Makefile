HERE = $(shell pwd)
BIN = $(HERE)/bin
BUILD_DIRS = bin build datamaps dist include \
	lib lib64 libmaxminddb man pngquant share
TESTS ?= ichnaea
TRAVIS ?= false

ICHNAEA_CFG ?= $(HERE)/ichnaea/tests/data/test.ini
GEOIP_PATH ?= $(HERE)/ichnaea/tests/data/GeoIP2-City-Test.mmdb

MAXMINDDB_VERSION = 1.2.1
MYSQL_DB = location
MYSQL_TEST_DB = test_location

DOCKER_BIN ?= docker
DOCKER_COMPOSE_BIN ?= docker-compose

MYSQL_HOST ?= localhost

ifeq ($(TRAVIS), true)
	MYSQL_USER ?= travis
	MYSQL_PWD ?=
	MYSQL_PORT ?= 3306
	DB_RW_URI ?= mysql+pymysql://$(MYSQL_USER)@$(MYSQL_HOST)/$(MYSQL_TEST_DB)
	DB_RO_URI ?= mysql+pymysql://$(MYSQL_USER)@$(MYSQL_HOST)/$(MYSQL_TEST_DB)

	REDIS_PORT ?= 6379

	PYTHON = python
	PIP = pip
	PYTEST = py.test
	CYTHON = cython
	SPHINXBUILD = sphinx-build
else
	MYSQL_USER ?= root
	MYSQL_PWD ?= mysql
	MYSQL_PORT ?= 33306
	DB_RW_URI ?= mysql+pymysql://$(MYSQL_USER):$(MYSQL_PWD)@$(MYSQL_HOST):$(MYSQL_PORT)/$(MYSQL_TEST_DB)
	DB_RO_URI ?= mysql+pymysql://$(MYSQL_USER):$(MYSQL_PWD)@$(MYSQL_HOST):$(MYSQL_PORT)/$(MYSQL_TEST_DB)

	REDIS_PORT ?= 36379

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

NODE_BIN = $(DOCKER_BIN) run --rm -it \
	--volume $(HERE):/app mozilla-ichnaea/node:latest


.PHONY: all mysql pip init_db test clean shell docs \
	docker docker-mysql docker-node docker-redis \
	build build_dev build_req build_cython \
	build_datamaps build_maxmind build_pngquant \
	release release_install release_compile \

all: build init_db

docker: docker-mysql docker-redis
ifneq ($(TRAVIS), true)
	$(DOCKER_COMPOSE_BIN) up -d
endif

docker-mysql:
ifneq ($(TRAVIS), true)
	cd docker/mysql; $(DOCKER_BIN) build -q -t mozilla-ichnaea/mysql:latest .
endif

docker-redis:
ifneq ($(TRAVIS), true)
	cd docker/redis; $(DOCKER_BIN) build -q -t mozilla-ichnaea/redis:latest .
endif

docker-node:
	cd docker/node; $(DOCKER_BIN) build -q -t mozilla-ichnaea/node:latest .

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

libmaxminddb/bootstrap:
	git clone --recursive git://github.com/maxmind/libmaxminddb
	cd libmaxminddb; git checkout 1.1.1
	cd libmaxminddb; git submodule update --init --recursive

libmaxminddb/Makefile:
	cd libmaxminddb; ./bootstrap
	cd libmaxminddb; ./configure --prefix=$(HERE)

lib/libmaxminddb.0.dylib: libmaxminddb/bootstrap libmaxminddb/Makefile
	cd libmaxminddb; make
	cd libmaxminddb; make install

build_maxmind: $(PYTHON) pip lib/libmaxminddb.0.dylib
	CFLAGS=-I$(HERE)/include LDFLAGS=-L$(HERE)/lib \
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
	DB_RW_URI=$(DB_RW_URI) DB_RO_URI=$(DB_RO_URI) $(BIN)/location_initdb \
		--alembic_ini=alembic.ini --location_ini=location.ini --initdb

css: docker-node
	$(NODE_BIN) make -f node.make css

js: docker-node
	$(NODE_BIN) make -f node.make js

clean:
	rm -rf $(BUILD_DIRS)
	rm -f $(HERE)/.coverage
	rm -f $(HERE)/*.log
	rm -rf $(HERE)/ichnaea.egg-info

test: mysql
	TESTING=true ICHNAEA_CFG=$(ICHNAEA_CFG) \
	DB_RW_URI=$(DB_RW_URI) \
	DB_RO_URI=$(DB_RO_URI) \
	GEOIP_PATH=$(GEOIP_PATH) \
	REDIS_PORT=$(REDIS_PORT) \
	LD_LIBRARY_PATH=$$LD_LIBRARY_PATH:$(HERE)/lib \
	$(PYTEST) $(TEST_ARG)

$(BIN)/sphinx-build:
	$(INSTALL) -r requirements/dev.txt

docs: $(BIN)/sphinx-build
	cd docs; SPHINXBUILD=$(SPHINXBUILD) make html
