#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage: docker/regenerate_requirements.sh
#
# Turns requirements/*.in into requirements/*.txt, with hashes
#
# This should be called from inside a container.

set -euo pipefail
IFS=$'\n\t'

REQS=(
  shared
  docs
  prod
  dev
)
export CUSTOM_COMPILE_COMMAND="make update-reqs"

cd /app

compile() {
    REQ_PATH=$1
    echo ">>> pip-compile ${REQ_PATH}"
    pip-compile --quiet --generate-hashes ${REQ_PATH}
}

for REQ in "${REQS[@]}"; do
    compile requirements/${REQ}.in
done
