#!/usr/bin/env bash

set -e

function check_versions_match {
    local versions=()
    while read l; do
        version=$(tomlq -r .package.version "$l")
        versions=("${versions[@]}" "$l":"$version")
    done < <(find -mindepth 2 -maxdepth 2 -type f -name Cargo.toml | sort)

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

if [ "$1" == "check" ]; then
    cargo clean
    cargo clippy -- -D warnings
    cargo fmt -- --check
    cargo check

    check_versions_match
fi

cargo build --release

pushd extension
./build.sh
popd
