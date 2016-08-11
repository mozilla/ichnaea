HERE = $(shell pwd)

NODE_BIN = docker run --rm -it \
	--volume $(HERE):/app mozilla/ichnaea_node:latest

.PHONY: all docker-node css js \
	release release_install release_compile

all:
	@echo 'No default make target defined.'

docker-node:
	cd docker/node; docker build -q -t mozilla/ichnaea_node:latest .

css: docker-node
	$(NODE_BIN) make -f node.make css

js: docker-node
	$(NODE_BIN) make -f node.make js

# These parts are called by the rpm spec file we use in deploying ichnaea.
release_install:
	$(HERE)/bin/pip install --no-deps -r requirements/build.txt
	$(HERE)/bin/pip install --no-deps --disable-pip-version-check \
		-r requirements/prod.txt
	$(HERE)/bin/python setup.py install

release_compile:
	$(HERE)/bin/python compile.py

release: release_install release_compile
