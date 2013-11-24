HERE = $(shell pwd)
BIN = $(HERE)/bin
PYTHON = $(BIN)/python

INSTALL = $(BIN)/pip install --no-deps
VTENV_OPTS ?= --distribute
TRAVIS ?= false

BUILD_DIRS = bin build include lib lib64 man share

MYSQL_TEST_DB = test_location
ifeq ($(TRAVIS), true)
	MYSQL_USER ?= travis
	MYSQL_PWD ?=
	SQLURI ?= mysql+pymysql://$(MYSQL_USER)@localhost/$(MYSQL_TEST_DB)
	SQLSOCKET ?=
else
	MYSQL_USER ?= root
	MYSQL_PWD ?= mysql
	SQLURI ?= mysql+pymysql://$(MYSQL_USER):$(MYSQL_PWD)@localhost/$(MYSQL_TEST_DB)
	SQLSOCKET ?= /opt/local/var/run/mysql56/mysqld.sock
endif

.PHONY: all test docs mysql

all: build

mysql:
ifeq ($(TRAVIS), true)
	mysql -u$(MYSQL_USER) -h localhost -e "create database $(MYSQL_TEST_DB)"
else
	mysql -u$(MYSQL_USER) -p$(MYSQL_PWD) -h localhost -e \
		"create database $(MYSQL_TEST_DB)" || echo
endif

$(PYTHON):
	virtualenv $(VTENV_OPTS) .

build: $(PYTHON)
	$(INSTALL) -r requirements/prod.txt
	$(INSTALL) -r requirements/test.txt
	$(PYTHON) setup.py develop
ifneq ($(TRAVIS), true)
	mysql -u$(MYSQL_USER) -p$(MYSQL_PWD) -h localhost -e \
		"create database location" || echo
endif


clean:
	rm -rf $(BUILD_DIRS)
	rm -f $(HERE)/.coverage
	rm -f $(HERE)/*.log
	rm -rf $(HERE)/ichnaea.egg-info

test: mysql
	SQLURI=$(SQLURI) SQLSOCKET=$(SQLSOCKET) CELERY_ALWAYS_EAGER=true \
	$(BIN)/nosetests -s -d -v --with-coverage --cover-package ichnaea ichnaea

bin/sphinx-build:
	bin/pip install Sphinx

docs:  bin/sphinx-build
	cd docs; make html
