#!/usr/bin/env bash

set -eEo pipefail

function usage() {
    echo "Usage: $0 [-f <remote>] [-l] <xpi_file>" 1>&2
    echo "    xpi_file    path of the XPI extension to test" 1>&2
    echo "    -f REMOTE   Fetch tag from specified REMOTE for backwards compatibility tests" 1>&2
    echo "    -o FILE     Write results as markdown to FILE" 1>&2
    echo "    -l          Test against latest available FF version. If not provided, the versions" 1>&2
    echo "                are read from the firefox_versions file." 1>&2
    exit "$1"
}

FETCH_REMOTE=
REPORT_MD_FILE=
FF_USE_LATEST=no

while getopts "f:o:lh" o; do
    case "${o}" in
        f)
            FETCH_REMOTE=${OPTARG}
            ;;
        o)
            REPORT_MD_FILE="${OPTARG}"
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


function run-suite() {
    local ff_version="$1"
    local xpi_file="$2"
    local host_target_version="$3"

    local invocation=( dbus-launch "$VIRTUALENV_DIR"/bin/python3 tabreport_tests.py "$ff_version" "$xpi_file" )
    tmpfile=
    if [ "$REPORT_MD_FILE" != "" ]; then
        echo "Outputting to ${REPORT_MD_FILE}" >&2
        tmpfile="$(mktemp)"
        invocation=( "${invocation[@]}" -o "$tmpfile" )
    fi

    result=0
    if [ "$host_target_version" != "" ]; then
        echo "Running integration tests with Firefox $ff_version and native host version ${host_target_version}" >&2
        echo "" >&2
        set +e
        HOST_TARGET_VERSION="$host_target_version" "${invocation[@]}"
        result=$?
        set -e
    else
        echo "Running integration tests with Firefox $ff_version" >&2
        echo "" >&2
        set +e
        "${invocation[@]}"
        result=$?
        set -e
    fi

    if [ "$REPORT_MD_FILE" != "" ]; then
        cat "$tmpfile" >> "$REPORT_MD_FILE"
    fi

    return "$result"
}

while read -r ff_version; do
    run-suite "$ff_version" "$xpi_file"
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
    run-suite "$ff_version" "$xpi_file" "$HOST_TARGET_VERSION"
    # Execute against latest FF version only
done < <(get-ff-versions | tail -n 1)
