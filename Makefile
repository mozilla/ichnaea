# This file is deprecated. It is only used by the rpm spec file
# Mozilla currently uses to deploy ichnaea.

HERE = $(shell pwd)

.PHONY: all release release_install release_compile

all:
	@echo 'No default make target defined.'

release_install:
	$(HERE)/bin/pip install --no-deps -r requirements/build.txt
	$(HERE)/bin/pip install --no-deps --disable-pip-version-check \
		-r requirements/prod.txt
	$(HERE)/bin/python setup.py install

release_compile:
	$(HERE)/bin/python compile.py

release: release_install release_compile
