#!/bin/sh
# Runs a command in the project image as the owner of the datasets folder, so the
# files the containers write (dataset copies) belong to the member whose project
# folder it is.
# @relation(REQ-AUT-006, scope=file)

# Stops at the first failing command (-e), so the command never starts as the wrong
# user when the datasets folder is missing, and at a variable that was never set (-u),
# instead of reading it as empty text.
set -eu

# User and group number of the folder's owner on the member's machine, for example
# 1000 and 1000; stat -c %u prints a file's user number, %g its group number.
owner=$(stat -c %u /app/datasets)
group=$(stat -c %g /app/datasets)

# The owner has no account in the image: HOME and USER give tools such as DVC a home
# folder and a user name.
#
# setpriv starts the command as that user and group instead of root: --reuid sets the
# user number, --regid the group number, both the real one (who started the command)
# and the effective one (what it may access); --clear-groups drops root's other
# groups. "$@" is the command this script was given, for example python -m
# forecasting.commands load. exec lets the command take this script's place, so it
# receives Docker's stop signal directly.
exec env HOME=/tmp USER=forecasting \
    setpriv --reuid="$owner" --regid="$group" --clear-groups "$@"
