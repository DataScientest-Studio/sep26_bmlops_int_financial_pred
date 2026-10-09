#!/usr/bin/env bash
# Converts docs/requirements.sdoc into docs/requirements.md for reading.
set -euo pipefail

cd "$(dirname "$0")/../docs"

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

mkdir "$tmp_dir/in"
cp requirements.sdoc "$tmp_dir/in/"
uvx strictdoc@0.30.1 export "$tmp_dir/in" --formats markdown --output-dir "$tmp_dir/out" > /dev/null

echo "<!-- Generated from requirements.sdoc by tools/export-requirements.sh. Do not edit. -->" > requirements.md
echo >> requirements.md
cat "$tmp_dir/out/markdown/requirements.md" >> requirements.md

echo "Written: docs/requirements.md"
