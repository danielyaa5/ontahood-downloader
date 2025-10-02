#!/usr/bin/env bash
# Zip all files that are NOT ignored by git, excluding any dot files/dirs and any *.app.zip bundles.
# The resulting archive is written to the user's Downloads folder.
#
# Usage:
#   scripts/zip_not_ignored.sh
#
# Notes:
# - Uses `git ls-files --cached --others --exclude-standard` to select files tracked or
#   untracked-but-not-ignored.
# - Excludes any path containing a dot-segment (e.g., .git, .vscode, .env) and any file
#   ending with .app.zip.
# - Writes zip to "$HOME/Downloads/<repo-name>-YYYYMMDD-HHMMSS.zip".

set -euo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: not inside a git repository" >&2
  exit 1
fi

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

repo_name=$(basename "$repo_root")
ts=$(date +%Y%m%d-%H%M%S)
dest_dir="$HOME/Downloads"
zip_path="$dest_dir/${repo_name}-${ts}.zip"

mkdir -p "$dest_dir"

tmp_list=$(mktemp)
cleanup() { rm -f "$tmp_list"; }
trap cleanup EXIT

# Collect files: tracked + untracked (not ignored), then filter
# - remove any path containing a dot segment at start or in subdirs (e.g., .git, .vscode, .env, etc.)
# - remove any .app.zip bundles
# - remove empty lines (safety)
# Note: newline-separated paths are used here. Paths with newlines are extremely rare.

git ls-files --cached --others --exclude-standard \
  | grep -Ev '(^\.|/\.)' \
  | grep -Ev '\.app\.zip$' \
  | grep -v '^$' \
  > "$tmp_list"

# Create zip from list
# -q: quiet
# -X: eXclude extra file attributes for better reproducibility
# -@: read file list from stdin
zip -q -X -@ "$zip_path" < "$tmp_list"

echo "Created: $zip_path"
