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
	@echo "  run              - run webapp, scheduler, and worker"
	@echo "  runservices      - run service containers (mysql, redis, etc)"
	@echo "  stop             - stop all service containers"
	@echo ""
	@echo "  shell            - open a shell in the app container"
	@echo "  clean            - remove all build, test, coverage and Python artifacts"
	@echo "  lint             - lint code"
	@echo "  test             - run unit tests"
	@echo "  testshell        - open a shell for running tests"
	@echo "  docs             - generate Sphinx HTML documentation, including API docs"
	@echo ""
	@echo "  setup            - set up mysql, redis, etc"
	@echo "  help             - see this text"
	@echo ""
	@echo "See https://mozilla.github.io/ichnaea/ for more documentation."

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
	    app web
	touch .docker-build

.PHONY: shell
shell: my.env .docker-build
	${DC} run --rm app shell

.PHONY: test
test: my.env .docker-build
	${DC} run --rm app shell ./docker/run_tests.sh ${ARGS}

.PHONY: docs
docs: my.env
	${DC} run --rm --no-deps app shell ./docker/run_build_docs.sh

.PHONY: lint
lint: my.env
	${DC} run --rm --no-deps app shell flake8 ichnaea

.PHONY: run
run: my.env
	${DC} up web

.PHONY: runservices
runservices: my.env
	${DC} up -d redis mysql

.PHONY: stop
stop: my.env
	${DC} stop
