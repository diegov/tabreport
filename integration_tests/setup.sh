#!/usr/bin/env bash

virtualenv_path="$1"

if [ "$virtualenv_path" ==  "" ]; then
    virtualenv_path="$PWD"/venv
fi

if [ ! -f "$virtualenv_path"/bin/activate ]; then
    python3 -m venv --system-site-packages "$virtualenv_path"
fi

source "$virtualenv_path"/bin/activate

pip install -r requirements.txt
