#!/bin/sh
# Runs a command in the project image as the owner of the models folder, so the models
# the containers write belong to the member whose project folder it is.
# @relation(REQ-AUT-006, scope=file)
set -eu

exec setpriv --reuid="$(stat -c %u /app/models)" --regid="$(stat -c %g /app/models)" \
    --clear-groups "$@"
