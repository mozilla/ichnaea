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

export CUSTOM_COMPILE_COMMAND="make update-reqs"
cd /app
echo ">>> pip-compile --quiet --generate-hashes requirements.in"
pip-compile --quiet --generate-hashes requirements.in
