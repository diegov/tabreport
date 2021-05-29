#!/usr/bin/env bash

set -e

THIS_SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

function manifest-attribute {
    python3 -c "import json; import sys

with open('manifest.json', 'r', encoding='utf-8') as f:
     print(json.load(f)[sys.argv[1]].lower())
" "$1"
}

version="$(manifest-attribute version)"

npm install

PATH="$THIS_SCRIPT_DIR"/node_modules/.bin/:"$PATH"

mkdir -p icons
node make-icon.js

build_opts=(-i make-icon.js build.sh package.json package-lock.json)

web-ext lint "${build_opts[@]}"
web-ext build --overwrite-dest "${build_opts[@]}"

name="$(manifest-attribute name)"

outputzip=web-ext-artifacts/"${name}-${version}.zip"
cp "$outputzip" ./"${name}-${version}.xpi"
