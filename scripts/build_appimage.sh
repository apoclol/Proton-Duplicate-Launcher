#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
VERSION=$(cd "$ROOT" && python3 -c 'from protondupe_launcher import __version__; print(__version__)')
ARCH=$(uname -m)
DIST_DIR="$ROOT/dist/linux/proton-dupe-launcher-${VERSION}-linux-${ARCH}"
APPDIR="$ROOT/build/appimage/ProtonDupeLauncher.AppDir"
APPIMAGE_TOOL=${APPIMAGE_TOOL:-appimagetool}
APPIMAGE_PATH="$ROOT/dist/linux/proton-dupe-launcher-${VERSION}-linux-${ARCH}.AppImage"

if [ ! -x "$DIST_DIR/proton-dupe-launcher" ]; then
  "$ROOT/scripts/build_linux.sh"
fi

if ! command -v "$APPIMAGE_TOOL" >/dev/null 2>&1; then
  printf 'appimagetool was not found.\n' >&2
  printf 'Install it first, then rerun this script.\n' >&2
  exit 1
fi

rm -rf "$APPDIR"
mkdir -p \
  "$APPDIR/usr/bin" \
  "$APPDIR/usr/lib/proton-dupe-launcher" \
  "$APPDIR/usr/share/applications" \
  "$APPDIR/usr/share/icons/hicolor/scalable/apps"

cp -a "$DIST_DIR/." "$APPDIR/usr/lib/proton-dupe-launcher/"
cp "$ROOT/packaging/linux/proton-dupe-launcher.desktop" "$APPDIR/proton-dupe-launcher.desktop"
cp "$ROOT/assets/linux/proton-dupe-launcher.svg" "$APPDIR/proton-dupe-launcher.svg"
cp "$ROOT/packaging/linux/proton-dupe-launcher.desktop" "$APPDIR/usr/share/applications/"
cp "$ROOT/assets/linux/proton-dupe-launcher.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
exec "$HERE/usr/lib/proton-dupe-launcher/proton-dupe-launcher" "$@"
EOF

cat > "$APPDIR/usr/bin/proton-dupe-launcher" <<'EOF'
#!/usr/bin/env sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
exec "$HERE/usr/lib/proton-dupe-launcher/proton-dupe-launcher" "$@"
EOF

chmod +x "$APPDIR/AppRun" "$APPDIR/usr/bin/proton-dupe-launcher"

ARCH_ENV="$ARCH"
if [ "$ARCH_ENV" = "amd64" ]; then
  ARCH_ENV="x86_64"
fi

ARCH="$ARCH_ENV" "$APPIMAGE_TOOL" "$APPDIR" "$APPIMAGE_PATH"
printf 'Built AppImage: %s\n' "$APPIMAGE_PATH"
