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

npm rebuild
npm install

PATH="$THIS_SCRIPT_DIR"/node_modules/.bin/:"$PATH"

mkdir -p icons
output_path="$PWD"/icons/tabreport.svg

pushd ../assets || exit 1
npm install
node make-icon.js "$output_path"
popd || exit 1

build_opts=(-i make-icon.js build.sh package.json package-lock.json icons/video.sh)

web-ext lint "${build_opts[@]}"
web-ext build --overwrite-dest "${build_opts[@]}"

name="$(manifest-attribute name)"

outputzip=web-ext-artifacts/"${name}-${version}.zip"
xpi_name="${name}-${version}.xpi"
cp "$outputzip" ./"$xpi_name"
echo "$PWD"/"$xpi_name" > artifact.txt

