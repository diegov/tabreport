#!/usr/bin/env bash

set -e

if [ "$1" == "check" ]; then
    cargo clean
    cargo clippy -- -D warnings
    cargo fmt -- --check
    cargo check
fi

cargo build --release

pushd extension
./build.sh
popd
