# Include my.env and export it so variables set in there are available
# in the Makefile.
include my.env
export

# Set these in the environment to override them. This is helpful for
# development if you have file ownership problems because the user
# in the container doesn't match the user on your host.
ICHNAEA_UID ?= 10001
ICHNAEA_GID ?= 10001
ICHNAEA_DOCKER_DB_ENGINE ?= mysql_5_7

# Set this in the environment to force --no-cache docker builds.
DOCKER_BUILD_OPTS :=
ifeq (1, ${NOCACHE})
DOCKER_BUILD_OPTS := --no-cache
endif

# Set this to override the cross-build paramters
BUILDX_PLATFORMS?=linux/amd64,linux/arm64
CROSS_BUILD_ARGS?=

DC := $(shell which docker-compose)
DOCKER := $(shell which docker)

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
	@echo "  runservices      - run service containers (database and redis)"
	@echo "  stop             - stop all service containers"
	@echo ""
	@echo "  shell            - open a shell in the app container"
	@echo "  dbshell          - open a database shell in the database container"
	@echo "  clean            - remove all build, test, coverage and Python artifacts"
	@echo "  lint             - lint code"
	@echo "  lintfix          - reformat code"
	@echo "  test             - run unit tests"
	@echo "  testcoverage     - run unit tests with coverage report"
	@echo "  testshell        - open a shell in the test environment"
	@echo "  docs             - generate Sphinx HTML documentation, including API docs"
	@echo "  assets           - build all generated static assets"
	@echo "  clean-assets     - remove generated static assets"
	@echo "  update-vendored  - re-download vendor source and test data"
	@echo "  update-reqs      - regenerate Python requirements"
	@echo "  local-map        - generate local map tiles"
	@echo "  cross-build      - build cross-platform docker containers"
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
	@if [ ! -f docker/node/npm-shrinkwrap.json ]; \
	then \
	echo "{}" > docker/node/npm-shrinkwrap.json; \
	fi
	${DC} build ${DOCKER_BUILD_OPTS} \
	    --build-arg userid=${ICHNAEA_UID} \
	    --build-arg groupid=${ICHNAEA_GID} \
	    node app
	${DC} build ${DOCKER_BUILD_OPTS} \
	    redis db
	touch .docker-build

.PHONY: cross-build
cross-build: my.env
	${DOCKER} buildx create --node ichnaea-cross-build --use
	${DOCKER} buildx build \
	    --platform ${BUILDX_PLATFORMS} \
	    --build-arg userid=${ICHNAEA_UID} \
	    --build-arg groupid=${ICHNAEA_GID} \
	    ${CROSS_BUILD_ARGS} \
	    .

.PHONY: setup
setup: my.env
	${DC} run app shell ./docker/run_setup.sh

.PHONY: shell
shell: my.env .docker-build
	${DC} run --rm app shell

.PHONY: dbshell
dbshell: my.env .docker-build
	${DC} up -d db
	${DC} exec db mysql --user root --password=location location

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

.PHONY: assets
assets: my.env .docker-build
	${DC} run --rm --user ${ICHNAEA_UID} node make -f node.make

.PHONY: clean-assets
clean-assets: my.env .docker-build
	${DC} run --rm --user ${ICHNAEA_UID} node make -f node.make clean

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
	${DC} up -d redis db

.PHONY: stop
stop: my.env
	${DC} stop

.PHONY: update-vendored
update-vendored: my.env
	${DC} run --rm --no-deps app shell make -f docker.make update_vendored

.PHONY: update-reqs
update-reqs: my.env
	${DC} run --rm --no-deps app shell ./docker/run_update_requirements.sh

.PHONY: local-map
local-map: my.env .docker-build
	${DC} run --rm app shell ./docker/run_local_map.sh
