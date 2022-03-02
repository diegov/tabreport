#!/usr/bin/env bash

set -e
set -o pipefail

xpi_file="$1"

# TODO: Cleanup
TMP_HOME=$(mktemp -d)
mkdir -p "$TMP_HOME"/.local/bin/

pushd .. || exit 1
./install_native.sh "$TMP_HOME"

popd || exit 1

export XDG_CACHE_HOME="$HOME"/.cache/
export HOME="$TMP_HOME"

./setup.sh venv

export PATH="$TMP_HOME"/.local/bin:"$PATH"
dbus-launch venv/bin/python3 tabreport_tests.py 86.0b9 "$xpi_file"
dbus-launch venv/bin/python3 tabreport_tests.py 98.0b9 "$xpi_file"
