#!/usr/bin/env bash

BINPATH=~/.local/bin
NATIVE_MANIFEST_DIR=~/.mozilla/native-messaging-hosts/

echo "Installing binaries to ${BINPATH}"
echo ""

if ! which strip >/dev/null; then
    function strip {
        echo "Strip tool not available, skipping...">&2
    }
fi

function install-binary {
    path="$1"
    name="$2"
    dst_path="$BINPATH"/"$name"
    cp -f "$path" "$dst_path" && strip "$dst_path"
}

set -e

cargo build -p tabreport_host --release 
install-binary target/release/tabreport_host tabreport_host

mkdir -p "$NATIVE_MANIFEST_DIR"

cargo build -p tabreport_client --release
install-binary target/release/tabreport_client tabreport
