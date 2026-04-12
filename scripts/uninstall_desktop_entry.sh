#!/usr/bin/env sh
set -eu

LOCAL_BIN="$HOME/.local/bin"
LOCAL_APPS="$HOME/.local/share/applications"
LOCAL_ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
WRAPPER_TARGET="$LOCAL_BIN/proton-dupe-launcher"
DESKTOP_TARGET="$LOCAL_APPS/proton-dupe-launcher.desktop"
ICON_TARGET="$LOCAL_ICONS/proton-dupe-launcher.svg"

rm -f "$WRAPPER_TARGET" "$DESKTOP_TARGET" "$ICON_TARGET"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$LOCAL_APPS" >/dev/null 2>&1 || true
fi

printf 'Desktop entry removed.\n'
printf 'Removed launcher: %s\n' "$WRAPPER_TARGET"
printf 'Removed desktop file: %s\n' "$DESKTOP_TARGET"
printf 'Removed icon: %s\n' "$ICON_TARGET"
printf '%s\n' 'Copied prefixes in ~/.local/share/proton-dupe-prefixes were left in place.'
