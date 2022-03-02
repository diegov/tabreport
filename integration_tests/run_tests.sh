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

if [ "$XDG_CACHE_HOME" == "" ]; then
    export XDG_CACHE_HOME="$HOME"/.cache/
fi

if [ "$VIRTUALENV_DIR" == "" ]; then
    VIRTUALENV_DIR="$PWD"/venv
fi

export HOME="$TMP_HOME"

./setup.sh "$VIRTUALENV_DIR"

export PATH="$TMP_HOME"/.local/bin:"$PATH"

while read -r ff_version; do
    if [ "$ff_version" != "" ]; then
        echo "Running integration tests with Firefox $ff_version" >&2
        echo "" >&2
        dbus-launch "$VIRTUALENV_DIR"/bin/python3 tabreport_tests.py "$ff_version" "$xpi_file"
    fi
done < firefox_versions
