#!/usr/bin/env sh
# Start CodeBuddy: the overlay starts the brain and stops it when you quit (right-click → Esci).
here="$(cd "$(dirname "$0")" && pwd)"
exec "$here/overlay/codebuddy-overlay" --start-brain "\"$here/brain/buddy\" serve" "$@"
