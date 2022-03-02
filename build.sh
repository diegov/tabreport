#!/usr/bin/env bash

set -e

function check_versions_match {
    local versions=()
    while read -r l; do
        version=$(tomlq -r .package.version "$l")
        versions=("${versions[@]}" "$l":"$version")
    done < <(find . -mindepth 2 -maxdepth 2 -type f -name Cargo.toml | sort)

    manifest=extension/manifest.json
    js_version=$(jq -r .version "$manifest")
    versions=("${versions[@]}" "$manifest":"$js_version")

    version_count=$(echo "${versions[@]}" | xargs -n 1 | cut -d':' -f 2 | sort | uniq | wc -l)
    if [ "$version_count" -ne 1 ]; then
        echo "Package versions don't match:" >&2
        echo >&2
        echo "${versions[@]}" | xargs -n 1 >&2
        echo >&2
        return 1
    fi
}

source ./rustflags

if [ "$1" == "check" ]; then
    check_versions_match

    cargo clean
    cargo clippy -- -D warnings
    cargo fmt -- --check
    cargo check
fi

cargo build --release

pushd extension
./build.sh
xpi_file="$(cat artifact.txt)"
popd

declare TMP_HOME

function cleanup {
    if [ -d "$TMP_HOME" ]; then
        rm -rf "$TMP_HOME"
    fi
}

trap cleanup ERR EXIT

if [ "$1" == "integration" ]; then
    pushd integration_tests || exit 1
    ./run_tests.sh "$xpi_file"
    popd || exit 1
fi
