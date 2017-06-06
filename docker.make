# This makefile is executed from inside the docker container.

HERE = $(shell pwd)
BIN = $(HERE)/bin
PYTHON = $(BIN)/python
INSTALL = $(BIN)/pip install --no-cache-dir \
	--disable-pip-version-check --require-hashes

DATAMAPS_DOWNLOAD = https://github.com/ericfischer/datamaps/archive
DATAMAPS_COMMIT = 76e620adabbedabd6866b23b30c145b53bae751e
DATAMAPS_NAME = datamaps-$(DATAMAPS_COMMIT)

LIBMAXMIND_DOWNLOAD = https://github.com/maxmind/libmaxminddb/releases/download
LIBMAXMIND_VERSION = 1.2.1
LIBMAXMIND_NAME = libmaxminddb-$(LIBMAXMIND_VERSION)

TESTS ?= ichnaea
ifeq ($(TESTS), ichnaea)
	TEST_ARG = --cov-config=.coveragerc --cov=ichnaea ichnaea
else
	TEST_ARG = $(TESTS)
endif

.PHONY: all build_datamaps build_libmaxmind build_deps \
	build_python_deps build_ichnaea build_check \
	docs

all:
	@echo "No default make step."

build_datamaps:
	wget -q $(DATAMAPS_DOWNLOAD)/$(DATAMAPS_COMMIT).tar.gz
	tar zxf $(DATAMAPS_COMMIT).tar.gz
	rm -f $(DATAMAPS_COMMIT).tar.gz
	cd $(DATAMAPS_NAME); make -s all
	cp $(DATAMAPS_NAME)/encode /usr/local/bin/
	cp $(DATAMAPS_NAME)/enumerate /usr/local/bin/
	cp $(DATAMAPS_NAME)/merge /usr/local/bin/
	cp $(DATAMAPS_NAME)/render /usr/local/bin/
	rm -rf $(HERE)/$(DATAMAPS_NAME)

build_libmaxmind:
	wget -q $(LIBMAXMIND_DOWNLOAD)/$(LIBMAXMIND_VERSION)/$(LIBMAXMIND_NAME).tar.gz
	tar xzf $(LIBMAXMIND_NAME).tar.gz
	rm -f $(LIBMAXMIND_NAME).tar.gz
	cd $(LIBMAXMIND_NAME); ./configure && make -s && make install
	ldconfig
	rm -rf $(HERE)/$(LIBMAXMIND_NAME)/

build_deps: build_datamaps build_libmaxmind

build_python_deps:
	pip install --no-cache-dir --disable-pip-version-check virtualenv
	python -m virtualenv --no-site-packages .
	$(INSTALL) -r requirements/build.txt
	$(INSTALL) -r requirements/all.txt

build_ichnaea:
	$(BIN)/cythonize -f ichnaea/geocalc.pyx
	$(BIN)/pip install -e .
	$(PYTHON) -c "from compileall import compile_dir; compile_dir('ichnaea', quiet=True)"

build_check:
	@which encode enumerate merge render pngquant
	$(PYTHON) -c "import sys; from shapely import speedups; sys.exit(not speedups.available)"
	$(PYTHON) -c "from ichnaea import geocalc"
	$(PYTHON) -c "import sys; from ichnaea.geoip import GeoIPWrapper; sys.exit(not GeoIPWrapper('ichnaea/tests/data/GeoIP2-City-Test.mmdb').check_extension())"
	$(PYTHON) -c "import sys; from ichnaea.geocode import GEOCODER; sys.exit(not GEOCODER.region(51.5, -0.1) == 'GB')"

docs:
	cd docs; SPHINXBUILD=$(BIN)/sphinx-build make html

test:
	TESTING=true $(BIN)/pytest $(TEST_ARG)
	$(BIN)/flake8 ichnaea
