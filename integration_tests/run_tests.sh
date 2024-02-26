#!/usr/bin/env bash

set -e
set -o pipefail

function usage() {
    echo "Usage: $0 [-f <remote>] [-l] <xpi_file>" 1>&2
    echo "    xpi_file    path of the XPI extension to test" 1>&2
    echo "    -f          Fetch tag from specified remote for backwards compatibility tests" 1>&2
    echo "    -l          Test against latest available FF version. If not provided, the versions" 1>&2
    echo "                are read from the firefox_versions file." 1>&2
    exit "$1"
}

FETCH_REMOTE=
FF_USE_LATEST=no

while getopts "f:lh" o; do
    case "${o}" in
        f)
            FETCH_REMOTE=${OPTARG}
            ;;
        l)
            FF_USE_LATEST=yes
            ;;
        h)
            usage 0
            ;;
        *)
            usage 1
            ;;
    esac
done
shift $((OPTIND-1))

xpi_file=$1

if [ "$xpi_file" == "" ]; then
    usage 1
fi

START_DIR="$PWD"

declare TMP_HOME
function cleanup() {
    echo "Cleanup temporary files" >&2
    if [ -d "$TMP_HOME" ]; then
        rm -rf "$TMP_HOME"
    fi

    pushd "$START_DIR" && git worktree prune
}

trap cleanup ERR EXIT

TMP_HOME=$(mktemp -d)
ORIGINAL_HOME="$HOME"

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

FF_VERSION=
if [ "$FF_USE_LATEST" == yes ]; then
    FF_VERSION=$("$VIRTUALENV_DIR"/bin/python3 -c 'import firefox; print(firefox.get_latest_available_version())')
fi

function get-ff-versions {
    if [ "$FF_VERSION" != "" ]; then
        echo "$FF_VERSION"
    else
        grep '..*' firefox_versions
    fi
}

export HOME="$TMP_HOME"

./setup.sh "$VIRTUALENV_DIR"

export PATH="$TMP_HOME"/.local/bin:"$PATH"

while read -r ff_version; do
    echo "Running integration tests with Firefox $ff_version" >&2
    echo "" >&2
    dbus-launch "$VIRTUALENV_DIR"/bin/python3 tabreport_tests.py "$ff_version" "$xpi_file"
done < <(get-ff-versions)

# Backwards compatibility test, since extensions are likely updated automatically
# whereas the native host is updated manually
HOST_TARGET_VERSION=0.1.9
HOST_TARGET_GIT_TAG=v"$HOST_TARGET_VERSION"

mkdir -p "$TMP_HOME"/oldversion

if [ "$FETCH_REMOTE" != "" ]; then
    git fetch "$FETCH_REMOTE" 'refs/tags/*:refs/tags/*'
    git fetch "$FETCH_REMOTE" "$HOST_TARGET_GIT_TAG" --depth 1
fi

git worktree add "$TMP_HOME"/oldversion

pushd "$TMP_HOME"/oldversion || exit 1
git checkout "$HOST_TARGET_GIT_TAG"
HOME="$ORIGINAL_HOME" ./install_native.sh "$TMP_HOME"
popd || exit 1

while read -r ff_version; do
    if [ "$ff_version" != "" ]; then
        echo "Running integration tests with Firefox $ff_version and native host version ${HOST_TARGET_VERSION}" >&2
        echo "" >&2
        HOST_TARGET_VERSION="$HOST_TARGET_VERSION" dbus-launch "$VIRTUALENV_DIR"/bin/python3 tabreport_tests.py "$ff_version" "$xpi_file"
    fi
    # Execute against latest FF version only
done < <(get-ff-versions | tail -n 1)
