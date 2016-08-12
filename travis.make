HERE = $(shell pwd)
INSTALL = pip install --no-deps --disable-pip-version-check

LIBMAXMIND_DOWNLOAD = https://github.com/maxmind/libmaxminddb/releases/download
LIBMAXMIND_VERSION = 1.1.1
LIBMAXMIND_NAME = libmaxminddb-$(LIBMAXMIND_VERSION)
MAXMINDDB_VERSION = 1.2.1

.PHONY: all pip build test build_maxmind

all: build

lib/libmaxminddb.0.dylib:
	wget -q $(LIBMAXMIND_DOWNLOAD)/$(LIBMAXMIND_VERSION)/$(LIBMAXMIND_NAME).tar.gz
	tar xzvf $(LIBMAXMIND_NAME).tar.gz
	rm -f $(LIBMAXMIND_NAME).tar.gz
	mv $(LIBMAXMIND_NAME) libmaxminddb
	cd libmaxminddb; ./configure --prefix=$(HERE) && make && make install

build_maxmind: lib/libmaxminddb.0.dylib
	CFLAGS=-I$(HERE)/include LDFLAGS=-L$(HERE)/lib \
		$(INSTALL) --no-binary :all: maxminddb==$(MAXMINDDB_VERSION)

pip:
	virtualenv .
	bin/pip install --disable-pip-version-check -r requirements/build.txt

build: pip build_maxmind
	$(INSTALL) -r requirements/prod.txt
	$(INSTALL) -r requirements/dev.txt
	cython ichnaea/geocalc.pyx
	python setup.py build_ext --inplace
	$(INSTALL) -e .
	python compile.py
	mysql -utravis -h localhost -e \
		"CREATE DATABASE IF NOT EXISTS location" || echo

test:
	TESTING=true ICHNAEA_CFG=$(HERE)/ichnaea/tests/data/test.ini \
	DB_RW_URI="mysql+pymysql://travis@localhost/location" \
	DB_RO_URI="mysql+pymysql://travis@localhost/location" \
	GEOIP_PATH=$(HERE)/ichnaea/tests/data/GeoIP2-City-Test.mmdb \
	REDIS_HOST=localhost REDIS_PORT=6379 \
	LD_LIBRARY_PATH=$$LD_LIBRARY_PATH:$(HERE)/lib \
	py.test --durations=10 --cov-config=.coveragerc --cov=ichnaea ichnaea
