#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
LOCAL_BIN="$HOME/.local/bin"
LOCAL_APPS="$HOME/.local/share/applications"
LOCAL_ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
WRAPPER_TARGET="$LOCAL_BIN/proton-dupe-launcher"
DESKTOP_TARGET="$LOCAL_APPS/proton-dupe-launcher.desktop"
ICON_TARGET="$LOCAL_ICONS/proton-dupe-launcher.svg"

if [ -x "$SCRIPT_DIR/proton-dupe-launcher" ]; then
  APP_ROOT="$SCRIPT_DIR"
  ICON_SOURCE="$APP_ROOT/share/icons/hicolor/scalable/apps/proton-dupe-launcher.svg"
  EXEC_MODE="dist"
else
  APP_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
  ICON_SOURCE="$APP_ROOT/assets/linux/proton-dupe-launcher.svg"
  EXEC_MODE="source"
fi

mkdir -p "$LOCAL_BIN" "$LOCAL_APPS" "$LOCAL_ICONS"
cp "$ICON_SOURCE" "$ICON_TARGET"

if [ "$EXEC_MODE" = "dist" ]; then
  {
    printf '%s\n' '#!/usr/bin/env sh'
    printf '%s\n' 'set -eu'
    printf 'exec "%s/proton-dupe-launcher" "$@"\n' "$APP_ROOT"
  } > "$WRAPPER_TARGET"
else
  {
    printf '%s\n' '#!/usr/bin/env sh'
    printf '%s\n' 'set -eu'
    printf 'exec python3 "%s/proton_dupe_launcher.py" "$@"\n' "$APP_ROOT"
  } > "$WRAPPER_TARGET"
fi

chmod +x "$WRAPPER_TARGET"

{
  printf '%s\n' '[Desktop Entry]'
  printf '%s\n' 'Version=1.0'
  printf '%s\n' 'Type=Application'
  printf '%s\n' 'Name=Proton Duplicate Launcher'
  printf '%s\n' 'Comment=Launch a second copy of a running non-Steam Proton game'
  printf 'Exec=%s\n' "$WRAPPER_TARGET"
  printf 'Icon=%s\n' "$ICON_TARGET"
  printf '%s\n' 'Terminal=false'
  printf '%s\n' 'Categories=Game;Utility;'
  printf '%s\n' 'Keywords=Proton;Steam;Wine;Launcher;Linux;'
  printf '%s\n' 'StartupNotify=true'
} > "$DESKTOP_TARGET"

chmod 0644 "$DESKTOP_TARGET"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$LOCAL_APPS" >/dev/null 2>&1 || true
fi

printf 'Desktop entry installed.\n'
printf 'Launcher: %s\n' "$WRAPPER_TARGET"
printf 'Desktop file: %s\n' "$DESKTOP_TARGET"
