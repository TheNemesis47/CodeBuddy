#!/usr/bin/env sh
# Adds CodeBuddy to your application menu (~/.local/share/applications), pointing at this folder.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
target="${XDG_DATA_HOME:-$HOME/.local/share}/applications/codebuddy.desktop"
mkdir -p "$(dirname "$target")"
sed "s|@DIR@|$here|g" "$here/codebuddy.desktop" > "$target"
chmod +x "$here/codebuddy.sh"
echo "CodeBuddy added to the application menu: $target"
