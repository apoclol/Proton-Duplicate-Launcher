# Proton Duplicate Launcher

Proton Duplicate Launcher is a Linux app for starting a second copy of a
non-Steam game that is already running through Steam with Proton.

It includes a small `tkinter` desktop app and a CLI for reusing the Proton
environment from a running game, so you can launch another instance without
rebuilding that setup by hand.

For most people, the easiest way to use it is to download a release archive,
extract it, and run the bundled program. You only need this source repository
if you want to inspect, modify, or rebuild the app yourself.

## What It Does

1. You start the first copy of your non-Steam game from Steam.
2. Proton Duplicate Launcher detects that already-running Proton process.
3. It reuses the detected Proton path, compatdata path, and launch context.
4. It starts a second copy of the same game.

The project includes:

- a simple desktop GUI
- CLI commands for listing and launching Proton-backed games
- optional copied-prefix launches when two instances should not share the same
  Proton prefix

It does not patch Steam or recreate every part of Steam's runtime stack.

## Requirements

If you are using the packaged release:

- Linux
- Steam
- a non-Steam shortcut already running through Proton
- no separate Python install is required

If you are running from source:

- Python 3.10 or newer
- `tkinter`
- on many distros this comes from a package such as `python3-tk`

## Use The Packaged Release

If you just want to run the app, this is the recommended path.

1. Download the Linux release archive from GitHub Releases.
2. Extract the archive.
3. Open the extracted folder.
4. Run `./proton-dupe-launcher`.

Inside the GUI:

1. Start your game in Steam first.
2. Click `Refresh`. The app automatically previews each detected process and
   only shows the ones that pass.
3. Select the detected game.
4. Click `Preview Launch` if you changed the EXE or copied-prefix settings and
   want to inspect the detected launch details. The GUI now confirms when that
   preview passes.
5. Click `Launch Second Copy` when ready.

If `Refresh` finds extra detected processes that do not pass the automatic
preview, use `Show More` in the GUI to inspect those hidden results.

Optional:

- Run `./install_desktop_entry.sh` from the extracted folder if you want it to
  show up like a normal desktop app.

Update a packaged install:

1. Download the newest Linux release archive.
2. Extract it to a new folder.
3. If you installed the desktop launcher before, run
   `./install_desktop_entry.sh` from the new extracted folder so the launcher
   points to the new version.
4. After confirming the new version works, delete the old extracted folder.

Uninstall a packaged install:

- If you only ran the app from its extracted folder, delete that folder.
- If you installed the desktop launcher, run `./uninstall_desktop_entry.sh`
  from the extracted folder.
- The app does not remove copied prefixes automatically. If you want to remove
  those too, check `~/.local/share/proton-dupe-prefixes/` first and delete only
  the folders you no longer want.

Important:

- Download the packaged release asset, not GitHub's automatic source-code
  archive.
- The packaged release already includes Python and the app runtime.

## Run From Source

Use this path if you want to inspect, modify, or rebuild the project.

### GUI

```bash
python3 proton_dupe_launcher.py
```

You can also launch the package entry point directly:

```bash
python3 -m protondupe_launcher
```

### Explicit GUI entry

```bash
python3 proton_dupe_launcher.py gui
```

### CLI Usage

List running Proton-backed candidates:

```bash
python3 proton_dupe_launcher.py list
```

Preview a launch:

```bash
python3 proton_dupe_launcher.py launch --pid 12345 --dry-run
```

Launch the second copy:

```bash
python3 proton_dupe_launcher.py launch --pid 12345
```

Override the detected executable:

```bash
python3 proton_dupe_launcher.py launch --pid 12345 --exe "/path/to/Game.exe"
```

Use a copied prefix:

```bash
python3 proton_dupe_launcher.py launch \
  --pid 12345 \
  --clone-prefix-to "$HOME/.local/share/proton-dupe-prefixes/my-game-second"
```

## Desktop Launcher From Source

If you want the source checkout to show up like a normal Linux app:

```bash
./scripts/install_desktop_entry.sh
```

That creates:

- `~/.local/bin/proton-dupe-launcher`
- `~/.local/share/applications/proton-dupe-launcher.desktop`
- `~/.local/share/icons/hicolor/scalable/apps/proton-dupe-launcher.svg`

To remove that desktop launcher later:

```bash
./scripts/uninstall_desktop_entry.sh
```

To update the desktop launcher after pulling new source changes:

```bash
./scripts/install_desktop_entry.sh
```

## Build A Packaged Linux Version

The main packaged format is a PyInstaller one-folder build.

### Install build dependencies

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
```

Before building, make sure the Python interpreter you are using can import
`tkinter`:

```bash
python -c "import tkinter; print(tkinter.TkVersion)"
```

### Build the package

```bash
./scripts/build_linux.sh
```

That creates:

- `dist/linux/proton-dupe-launcher-<version>-linux-<arch>/`
- `dist/linux/proton-dupe-launcher-<version>-linux-<arch>.tar.gz`

The extracted build includes:

- the bundled executable
- the app icon
- the desktop file
- `install_desktop_entry.sh`
- `uninstall_desktop_entry.sh`

So end users do not need Python installed separately.

### Install the packaged app locally

After extracting the built folder:

```bash
./install_desktop_entry.sh
```

To remove that local desktop launcher later:

```bash
./uninstall_desktop_entry.sh
```

## Update From Source

If you are running the project from a git checkout:

```bash
git pull
```

If build dependencies changed, refresh them too:

```bash
python -m pip install -r requirements-build.txt
```

If you use the source-based desktop launcher, rerun:

```bash
./scripts/install_desktop_entry.sh
```

## Optional AppImage Build

An AppImage build script is also included:

```bash
./scripts/build_appimage.sh
```

Notes:

- AppImage support depends on `appimagetool` already being installed and
  available on `PATH`.
- The PyInstaller folder build is the primary release format.

## Known Linux / Proton Limitations

- Linux only. No Windows or macOS support is planned.
- This tool is intended for non-Steam shortcuts launched through Steam with
  Proton.
- Some games simply do not allow multiple instances.
- Anti-cheat, launcher behavior, or account restrictions can still block this.
- The detected executable path may still require a manual override.
- Some games work better with a copied prefix than a shared prefix.
- Some games may need the full Steam runtime or container behavior rather than
  the direct Proton fallback path.
- If Steam's per-app launcher service is unavailable, the backend falls back to
  direct Proton launch. That can still work, but it is not identical to
  Steam's own launch path.
- When launched from sandboxed environments such as Flatpak-based editors, the
  app may need to re-exec on the host to see real Steam processes. It attempts
  to do that automatically with `flatpak-spawn` when available.

## Safety Notes

- Start with `Preview Launch` or `--dry-run` when testing a new game.
- Use a copied prefix if the two copies interfere with each other.
- Do not assume that success with one Proton title guarantees success with
  another.

## License

See [LICENSE](LICENSE).
