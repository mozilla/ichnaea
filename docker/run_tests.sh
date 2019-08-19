#!/bin/bash

# Run tests.
#
# Run this in the test container built using bin/test_env.sh.

pytest "$@"
