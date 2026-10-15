#!/usr/bin/env sh
# Adds CodeBuddy to your application menu (~/.local/share/applications), pointing at this folder.
# An entry you changed by hand is kept as codebuddy.desktop.bak, never overwritten silently.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
target="${XDG_DATA_HOME:-$HOME/.local/share}/applications/codebuddy.desktop"
mkdir -p "$(dirname "$target")"
new="$(mktemp)"
trap 'rm -f "$new"' EXIT
sed "s|@DIR@|$here|g" "$here/codebuddy.desktop" > "$new"
if [ -f "$target" ] && ! cmp -s "$new" "$target"; then
  cp "$target" "$target.bak"
  echo "Your previous entry is saved as $target.bak (copy your changes back from there)."
fi
cp "$new" "$target"
chmod +x "$here/codebuddy.sh"
echo "CodeBuddy added to the application menu: $target"
