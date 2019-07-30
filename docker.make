# This makefile is executed from inside the docker container.

HERE = $(shell pwd)
BIN = $(HERE)/bin
PYTHON = $(BIN)/python
INSTALL = MYSQLXPB_PROTOBUF_INCLUDE_DIR=/usr/include/google/protobuf \
	MYSQLXPB_PROTOBUF_LIB_DIR=/usr/lib/x86_64-linux-gnu \
	MYSQLXPB_PROTOC=/usr/bin/protoc \
	$(BIN)/pip install --no-cache-dir \
	--disable-pip-version-check --require-hashes

VENDOR = $(HERE)/vendor

DATAMAPS_COMMIT = 76e620adabbedabd6866b23b30c145b53bae751e
DATAMAPS_NAME = datamaps-$(DATAMAPS_COMMIT)
DATAMAPS_DIR = $(VENDOR)/$(DATAMAPS_NAME)

LIBMAXMIND_VERSION = 1.3.2
LIBMAXMIND_NAME = libmaxminddb-$(LIBMAXMIND_VERSION)
LIBMAXMIND_DIR = $(VENDOR)/$(LIBMAXMIND_NAME)

TESTS ?= ichnaea
ifeq ($(TESTS), ichnaea)
	TEST_ARG = --cov-config=.coveragerc --cov=ichnaea ichnaea
else
	TEST_ARG = $(TESTS)
endif

TEST_JUNIT_XML ?= none
ifneq ($(TEST_JUNIT_XML), none)
    TEST_ARG += --junitxml=$(TEST_JUNIT_XML)
endif

.PHONY: all build_datamaps build_libmaxmind build_deps \
	build_python_deps build_ichnaea build_check \
	docs

all:
	@echo "No default make step."

build_datamaps:
	cd $(VENDOR); tar zxf $(DATAMAPS_NAME).tar.gz
	cd $(DATAMAPS_DIR); make -s all
	cp $(DATAMAPS_DIR)/encode /usr/local/bin/
	cp $(DATAMAPS_DIR)/enumerate /usr/local/bin/
	cp $(DATAMAPS_DIR)/merge /usr/local/bin/
	cp $(DATAMAPS_DIR)/render /usr/local/bin/
	rm -rf $(DATAMAPS_DIR)

build_libmaxmind:
	cd $(VENDOR); tar xzf $(LIBMAXMIND_NAME).tar.gz
	cd $(LIBMAXMIND_DIR); ./configure && make -s && make install
	ldconfig
	rm -rf $(LIBMAXMIND_DIR)

build_deps: build_datamaps build_libmaxmind

build_python_deps:
	pip install --no-cache-dir --disable-pip-version-check virtualenv
	python -m virtualenv --no-site-packages .
	$(INSTALL) -r requirements/build.txt
	$(INSTALL) -r requirements/all.txt
	$(INSTALL) -r requirements/binary.txt

build_ichnaea:
	$(BIN)/cythonize -f ichnaea/geocalc.pyx
	$(BIN)/pip install -e .
	$(PYTHON) -c "from compileall import compile_dir; compile_dir('ichnaea', quiet=True)"

build_check:
	@which encode enumerate merge render pngquant
	$(PYTHON) -c "import sys; from mysql.connector import HAVE_CEXT; sys.exit(not HAVE_CEXT)"
	$(PYTHON) -c "import sys; from shapely import speedups; sys.exit(not speedups.available)"
	$(PYTHON) -c "from ichnaea import geocalc"
	$(PYTHON) -c "import sys; from ichnaea.geoip import GeoIPWrapper; sys.exit(not GeoIPWrapper('ichnaea/tests/data/GeoIP2-City-Test.mmdb').check_extension())"
	$(PYTHON) -c "import sys; from ichnaea.geocode import GEOCODER; sys.exit(not GEOCODER.region(51.5, -0.1) == 'GB')"

docs:
	cd docs; SPHINXBUILD=$(BIN)/sphinx-build make html

test:
	TESTING=true $(BIN)/pytest $(TEST_ARG)
	$(BIN)/flake8 ichnaea
