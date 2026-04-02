#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
VERSION=$(cd "$ROOT" && python3 -c 'from protondupe_launcher import __version__; print(__version__)')
ARCH=$(uname -m)
PYI_ROOT="$ROOT/build/pyinstaller"
PYI_DIST="$PYI_ROOT/dist"
OUTPUT_DIR="$ROOT/dist/linux/proton-dupe-launcher-${VERSION}-linux-${ARCH}"
ARCHIVE_PATH="$ROOT/dist/linux/proton-dupe-launcher-${VERSION}-linux-${ARCH}.tar.gz"

if ! python3 -m PyInstaller --version >/dev/null 2>&1; then
  printf 'PyInstaller is not installed for python3.\n' >&2
  printf 'Install build dependencies first with: python3 -m pip install -r requirements-build.txt\n' >&2
  exit 1
fi

if ! python3 -c 'import tkinter, tkinter.filedialog, tkinter.messagebox, tkinter.ttk' >/dev/null 2>&1; then
  printf 'The selected python3 does not have a working tkinter installation.\n' >&2
  printf 'Install your distro package first, for example: python3-tk\n' >&2
  exit 1
fi

rm -rf "$PYI_ROOT" "$OUTPUT_DIR"
mkdir -p "$PYI_DIST" "$ROOT/dist/linux"

cd "$ROOT"
python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$PYI_DIST" \
  --workpath "$PYI_ROOT/work" \
  packaging/pyinstaller/proton-dupe-launcher.spec

cp -a "$PYI_DIST/proton-dupe-launcher" "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/share/applications" "$OUTPUT_DIR/share/icons/hicolor/scalable/apps"
cp LICENSE README.md "$OUTPUT_DIR/"
cp packaging/linux/proton-dupe-launcher.desktop "$OUTPUT_DIR/share/applications/"
cp assets/linux/proton-dupe-launcher.svg "$OUTPUT_DIR/share/icons/hicolor/scalable/apps/"
cp scripts/install_desktop_entry.sh "$OUTPUT_DIR/"
chmod +x "$OUTPUT_DIR/install_desktop_entry.sh"

rm -f "$ARCHIVE_PATH"
tar -C "$ROOT/dist/linux" -czf "$ARCHIVE_PATH" "$(basename "$OUTPUT_DIR")"

printf 'Built folder: %s\n' "$OUTPUT_DIR"
printf 'Built archive: %s\n' "$ARCHIVE_PATH"
