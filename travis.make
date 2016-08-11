HERE = $(shell pwd)

MAXMINDDB_VERSION = 1.2.1

DB_NAME = location
DB_HOST ?= localhost
DB_PORT ?= 3306
DB_USER ?= travis
DB_RW_URI ?= mysql+pymysql://$(DB_USER)@$(DB_HOST):$(DB_PORT)/$(DB_NAME)
DB_RO_URI ?= mysql+pymysql://$(DB_USER)@$(DB_HOST):$(DB_PORT)/$(DB_NAME)

ICHNAEA_CFG ?= $(HERE)/ichnaea/tests/data/test.ini
GEOIP_PATH ?= $(HERE)/ichnaea/tests/data/GeoIP2-City-Test.mmdb

INSTALL = pip install --no-deps --disable-pip-version-check

.PHONY: all pip build test \
	build_datamaps build_maxmind build_pngquant

all: build

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

build_maxmind: lib/libmaxminddb.0.dylib
	CFLAGS=-I$(HERE)/include LDFLAGS=-L$(HERE)/lib \
		$(INSTALL) --no-binary :all: maxminddb==$(MAXMINDDB_VERSION)

pngquant/pngquant:
	git clone --recursive git://github.com/pornel/pngquant
	cd pngquant; git checkout 2.5.2
	cd pngquant; ./configure
	cd pngquant; make all

build_pngquant: pngquant/pngquant

pip:
	virtualenv .
	bin/pip install --disable-pip-version-check -r requirements/build.txt

build: pip build_datamaps build_maxmind build_pngquant
	$(INSTALL) -r requirements/prod.txt
	$(INSTALL) -r requirements/dev.txt
	cython ichnaea/geocalc.pyx
	python setup.py build_ext --inplace
	$(INSTALL) -e .
	python compile.py
	mysql -u$(DB_USER) -h $(DB_HOST) -e \
		"CREATE DATABASE IF NOT EXISTS $(DB_NAME)" || echo

test:
	TESTING=true ICHNAEA_CFG=$(ICHNAEA_CFG) \
	DB_RW_URI=$(DB_RW_URI) \
	DB_RO_URI=$(DB_RO_URI) \
	GEOIP_PATH=$(GEOIP_PATH) \
	REDIS_HOST=localhost REDIS_PORT=6379 \
	LD_LIBRARY_PATH=$$LD_LIBRARY_PATH:$(HERE)/lib \
	py.test --durations=10 --cov-config=.coveragerc --cov=ichnaea ichnaea
