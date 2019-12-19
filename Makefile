# Include my.env and export it so variables set in there are available
# in the Makefile.
include my.env
export

# Set these in the environment to override them. This is helpful for
# development if you have file ownership problems because the user
# in the container doesn't match the user on your host.
ICHNAEA_UID ?= 10001
ICHNAEA_GID ?= 10001

# Set this in the environment to force --no-cache docker builds.
DOCKER_BUILD_OPTS :=
ifeq (1, ${NOCACHE})
DOCKER_BUILD_OPTS := --no-cache
endif

DC := $(shell which docker-compose)

.PHONY: help
help: default

.PHONY: default
default:
	@echo "Usage: make RULE"
	@echo ""
	@echo "Ichnaea make rules:"
	@echo ""
	@echo "  build            - build docker containers"
	@echo "  setup            - drop and recreate service state"
	@echo "  run              - run webapp"
	@echo "  runcelery        - run scheduler and worker"
	@echo "  runservices      - run service containers (mysql, redis, etc)"
	@echo "  stop             - stop all service containers"
	@echo ""
	@echo "  shell            - open a shell in the app container"
	@echo "  mysql            - open mysql prompt"
	@echo "  clean            - remove all build, test, coverage and Python artifacts"
	@echo "  lint             - lint code"
	@echo "  lintfix          - reformat code"
	@echo "  test             - run unit tests"
	@echo "  testcoverage     - run unit tests with coverage report"
	@echo "  testshell        - open a shell in the test environment"
	@echo "  docs             - generate Sphinx HTML documentation, including API docs"
	@echo "  buildjs          - generate js static assets"
	@echo "  buildcss         - generate css static assets"
	@echo "  download         - re-download vendor source and test data"
	@echo ""
	@echo "  help             - see this text"
	@echo ""
	@echo "See https://ichnaea.readthedocs.io/ for more documentation."

.PHONY: clean
clean:
	rm .docker-build* || true

my.env:
	@if [ ! -f my.env ]; \
	then \
	echo "Copying my.env.dist to my.env..."; \
	cp docker/config/my.env.dist my.env; \
	fi

.docker-build:
	make build

.PHONY: build
build: my.env
	${DC} build ${DOCKER_BUILD_OPTS} \
	    --build-arg userid=${ICHNAEA_UID} \
	    --build-arg groupid=${ICHNAEA_GID} \
	    node app
	touch .docker-build

.PHONY: setup
setup: my.env
	${DC} run app shell ./docker/run_setup.sh

.PHONY: shell
shell: my.env .docker-build
	${DC} run --rm app shell

.PHONY: mysql
mysql: my.env .docker-build
	${DC} up -d mysql
	${DC} exec mysql mysql --user root --password=location location

.PHONY: test
test: my.env .docker-build
	./bin/test_env.sh

.PHONY: testcoverage
testcoverage: my.env .docker-build
	./bin/test_env.sh --cov=ichnaea --cov-branch

.PHONY: testshell
testshell: my.env .docker-build
	./bin/test_env.sh --shell

.PHONY: docs
docs: my.env .docker-build
	${DC} run --rm --no-deps app shell ./docker/run_build_docs.sh

.PHONY: buildjs
buildjs: my.env .docker-build
	${DC} run --rm --user ${ICHNAEA_UID} node make -f node.make js

.PHONY: buildcss
buildcss: my.env .docker-build
	${DC} run --rm --user ${ICHNAEA_UID} node make -f node.make css

.PHONY: lint
lint: my.env .docker-build
	${DC} run --rm --no-deps app shell ./docker/run_lint.sh

.PHONY: lintfix
lintfix: my.env .docker-build
	${DC} run --rm --no-deps app shell ./docker/run_lint.sh --fix

.PHONY: run
run: my.env .docker-build
	${DC} up web

.PHONY: runcelery
runcelery: my.env .docker-build
	${DC} up scheduler worker

.PHONY: runservices
runservices: my.env .docker-build
	${DC} up -d redis mysql

.PHONY: stop
stop: my.env
	${DC} stop

.PHONY: download
download: my.env
	${DC} run --rm --no-deps app shell make -f docker.make download
