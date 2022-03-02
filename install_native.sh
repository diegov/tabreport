#!/usr/bin/env bash

TARGET_HOME="$1"

if [ "$TARGET_HOME" == "" ]; then
    TARGET_HOME="$HOME"
fi

BINPATH="$TARGET_HOME"/.local/bin
NATIVE_MANIFEST_DIR="$TARGET_HOME"/.mozilla/native-messaging-hosts/

echo "Installing binaries to ${BINPATH}"
echo ""

function install-binary {
    path="$1"
    name="$2"
    dst_path="$BINPATH"/"$name"
    cp -f "$path" "$dst_path"
}

set -e

source ./rustflags

cargo build -p tabreport_host --release 
install-binary target/release/tabreport_host tabreport_host

mkdir -p "$NATIVE_MANIFEST_DIR"
host/make_host_manifest "$BINPATH"/tabreport_host "$NATIVE_MANIFEST_DIR"

cargo build -p tabreport_client --release
install-binary target/release/tabreport_client tabreport
