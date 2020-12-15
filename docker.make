# This makefile is executed from inside the docker container.

HERE = $(shell pwd)
PYTHON = $(shell which python)
PIP = $(shell which pip)

VENDOR = $(HERE)/vendor
TEST_DATA = $(HERE)/ichnaea/tests/data

DATAMAPS_COMMIT = 76e620adabbedabd6866b23b30c145b53bae751e
DATAMAPS_NAME = datamaps-$(DATAMAPS_COMMIT)
DATAMAPS_DIR = $(VENDOR)/$(DATAMAPS_NAME)

LIBMAXMIND_VERSION = 1.4.2
LIBMAXMIND_NAME = libmaxminddb-$(LIBMAXMIND_VERSION)
LIBMAXMIND_DIR = $(VENDOR)/$(LIBMAXMIND_NAME)

TESTS ?= ichnaea
ifeq ($(TESTS), ichnaea)
	TEST_ARG = --cov-config=.coveragerc --cov=ichnaea ichnaea
else
	TEST_ARG = $(TESTS)
endif

.PHONY: all build_datamaps build_libmaxmind build_deps \
	build_python_deps build_ichnaea build_check \
	docs

.PHONY: help
help: all

all:
	@echo "Usage: make RULE"
	@echo ""
	@echo "make rules:"
	@echo ""
	@echo "  build_deps        - build datamaps and libmaxmind"
	@echo "  build_python_deps - install and check python dependencies"
	@echo "  build_geocalc     - compile and install geocalclib"
	@echo "  check             - check that C libraries are available to Python"
	@echo "  update_vendored   - update libraries and test data"
	@echo ""
	@echo "  build_datamaps    - build datamaps binaries"
	@echo "  build_libmaxmind  - build libmaxmind library"
	@echo "  update_datamaps   - update datamaps source"
	@echo "  update_libmaxmind - update libmaxmind source"
	@echo "  update_test_data  - update MaxMind DB test data"
	@echo ""
	@echo "  help              - see this text"

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
	$(PIP) install --no-cache-dir --disable-pip-version-check --require-hashes \
	    -r requirements.txt
	$(PIP) check --disable-pip-version-check

build_geocalc:
	@which cythonize
	cythonize -f geocalclib/geocalc.pyx
	cd geocalclib && $(PIP) install --no-cache-dir --disable-pip-version-check .

build_check:
	@which encode enumerate merge render pngquant
	$(PYTHON) -c "import sys; from shapely import speedups; sys.exit(not speedups.available)"
	$(PYTHON) -c "import geocalc"
	$(PYTHON) -c "import sys; from ichnaea.geoip import GeoIPWrapper; sys.exit(not GeoIPWrapper('ichnaea/tests/data/GeoIP2-City-Test.mmdb').check_extension())"
	$(PYTHON) -c "import sys; from ichnaea.geocode import GEOCODER; sys.exit(not GEOCODER.region(51.5, -0.1) == 'GB')"

.PHONY: update_datamaps
update_datamaps:
	cd $(VENDOR) && wget -q \
	    -O $(DATAMAPS_NAME).tar.gz \
        https://github.com/ericfischer/datamaps/archive/$(DATAMAPS_COMMIT).tar.gz

.PHONY: update_libmaxmind
update_libmaxmind:
	cd $(VENDOR) && wget -q \
	    -O $(LIBMAXMIND_NAME).tar.gz \
	    https://github.com/maxmind/libmaxminddb/releases/download/$(LIBMAXMIND_VERSION)/$(LIBMAXMIND_NAME).tar.gz

.PHONY: update_test_data
update_test_data:
	cd $(TEST_DATA) && wget -q \
	    -O GeoIP2-City-Test.json \
	    https://raw.githubusercontent.com/maxmind/MaxMind-DB/master/source-data/GeoIP2-City-Test.json && \
	wget -q \
	    -O GeoIP2-City-Test.mmdb \
	    https://github.com/maxmind/MaxMind-DB/raw/master/test-data/GeoIP2-City-Test.mmdb && \
	wget -q \
	    -O GeoIP2-Connection-Type-Test.mmdb \
	    https://github.com/maxmind/MaxMind-DB/raw/master/test-data/GeoIP2-Connection-Type-Test.mmdb

.PHONY: update_vendored
update_vendored: update_datamaps update_libmaxmind update_test_data
