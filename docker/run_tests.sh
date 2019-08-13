#!/bin/bash

# Run tests.
#
# Run this in the app container.

TESTING=true pytest "$@"
