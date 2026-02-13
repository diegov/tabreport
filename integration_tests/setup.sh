#!/usr/bin/env bash

set -eEo pipefail

virtualenv_path="$1"

if [ "$virtualenv_path" ==  "" ]; then
    virtualenv_path="$PWD"/venv
fi

if [ ! -f "$virtualenv_path"/bin/activate ] || [ ! -f "$virtualenv_path"/bin/python3 ]; then
    echo "Creating new virtualenv at ${virtualenv_path}" >&2

    if [ -d "$virtualenv_path" ]; then
        rm -rf "$virtualenv_path"
    fi
    python3 -m venv --system-site-packages "$virtualenv_path"
else
    echo "Found usable virtualenv at ${virtualenv_path}" >&2
fi

source "$virtualenv_path"/bin/activate

pip install -r requirements.txt
