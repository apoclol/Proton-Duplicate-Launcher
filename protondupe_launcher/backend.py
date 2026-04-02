"""Backend launcher logic shared by the CLI and the GUI."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Callable, Dict, Iterable, List, Optional, Sequence


IMPORTANT_ENV_PREFIXES = (
    "STEAM_COMPAT_",
    "STEAM_RUNTIME",
    "PRESSURE_VESSEL",
    "PROTON",
)

SESSION_ENV_KEYS = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "DISPLAY",
    "XAUTHORITY",
    "WAYLAND_DISPLAY",
    "WAYLAND_SOCKET",
    "XDG_RUNTIME_DIR",
    "XDG_SESSION_TYPE",
    "XDG_SESSION_DESKTOP",
    "XDG_CURRENT_DESKTOP",
    "XDG_CONFIG_HOME",
    "XDG_CONFIG_DIRS",
    "XDG_DATA_HOME",
    "XDG_DATA_DIRS",
    "XDG_CACHE_HOME",
    "DBUS_SESSION_BUS_ADDRESS",
    "PULSE_SERVER",
    "PIPEWIRE_REMOTE",
    "FONTCONFIG_PATH",
    "FONTCONFIG_FILE",
)

NOISE_EXECUTABLE_NAMES = {
    "explorer.exe",
    "plugplay.exe",
    "rpcss.exe",
    "services.exe",
    "steam.exe",
    "svchost.exe",
    "tabtip.exe",
    "winedevice.exe",
    "wineserver",
    "xalia.exe",
}

DEFAULT_CLONE_PREFIX_DIR = (
    Path.home() / ".local" / "share" / "proton-dupe-prefixes"
)


@dataclass
class ProcessCandidate:
    """Represents a running process that looks like a Proton game instance."""

    pid: int
    command: str
    exe_hint: Optional[str]
    compat_data_path: Optional[str]
    proton_path: Optional[str]


def emit_message(
    message: str,
    reporter: Optional[Callable[[str], None]] = None,
) -> None:
    """Send output either to a callback or to standard output."""

    if reporter is None:
        print(message)
        return
    reporter(message)


def iter_proc_ids() -> Iterable[int]:
    """Yield numeric PIDs from /proc."""

    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            yield int(entry.name)


def read_environ(pid: int) -> Dict[str, str]:
    """Read a process environment from /proc/<pid>/environ."""

    environ_path = Path("/proc") / str(pid) / "environ"
    try:
        raw = environ_path.read_bytes()
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return {}

    env: Dict[str, str] = {}
    for chunk in raw.split(b"\0"):
        if not chunk or b"=" not in chunk:
            continue
        key, value = chunk.split(b"=", 1)
        env[key.decode("utf-8", errors="replace")] = value.decode(
            "utf-8", errors="replace"
        )
    return env


def read_cmdline(pid: int) -> List[str]:
    """Read a process command line from procfs."""

    cmdline_path = Path("/proc") / str(pid) / "cmdline"
    try:
        raw = cmdline_path.read_bytes()
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return []

    return [
        item.decode("utf-8", errors="replace")
        for item in raw.split(b"\0")
        if item
    ]


def read_cwd(pid: int) -> Optional[Path]:
    """Read a process working directory from procfs."""

    cwd_path = Path("/proc") / str(pid) / "cwd"
    try:
        return cwd_path.resolve()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return None


def looks_like_windows_program(text: str) -> bool:
    """Return True if the string looks like a Windows executable path."""

    lower = text.lower()
    return lower.endswith(".exe") or lower.endswith(".bat") or lower.endswith(".msi")


def guess_windows_exe(cmdline: List[str]) -> Optional[str]:
    """Try to infer the Windows executable from a Proton/Wine command line."""

    for item in reversed(cmdline):
        if looks_like_windows_program(item):
            return item
    return None


def find_proton_script(env: Dict[str, str]) -> Optional[str]:
    """Discover the Proton launcher script from the environment."""

    direct_candidates = []

    for key in ("PROTON_PATH", "STEAM_COMPAT_TOOL_PATH", "STEAM_COMPAT_TOOL_PATHS"):
        value = env.get(key)
        if value:
            direct_candidates.extend(value.split(":"))

    for candidate in direct_candidates:
        candidate_path = Path(candidate)
        if candidate_path.is_file() and candidate_path.name == "proton":
            return str(candidate_path)

        proton_script = candidate_path / "proton"
        if proton_script.is_file():
            return str(proton_script)

    return None


def resolve_app_id(source_env: Dict[str, str], compat_data_path: Path) -> Optional[str]:
    """Determine the Steam app id associated with the running Proton process."""

    for key in ("STEAM_COMPAT_APP_ID", "SteamAppId", "STEAM_GAME_ID"):
        value = source_env.get(key)
        if value and value.isdigit() and value != "0":
            return value

    fallback = compat_data_path.name
    if fallback.isdigit():
        return fallback

    return None


def find_runtime_launch_client(
    source_env: Dict[str, str],
    proton_script: str,
) -> Optional[str]:
    """Locate Steam's command-injection client for the current runtime."""

    candidates = []

    pressure_vessel_prefix = source_env.get("PRESSURE_VESSEL_PREFIX")
    if pressure_vessel_prefix:
        candidates.append(
            Path(pressure_vessel_prefix) / "bin" / "steam-runtime-launch-client"
        )

    runtime_base = source_env.get("PRESSURE_VESSEL_RUNTIME_BASE")
    if runtime_base:
        candidates.append(
            Path(runtime_base) / "pressure-vessel" / "bin" / "steam-runtime-launch-client"
        )

    common_root = Path(proton_script).expanduser().resolve().parent.parent
    candidates.extend(
        [
            common_root
            / "SteamLinuxRuntime_sniper"
            / "pressure-vessel"
            / "bin"
            / "steam-runtime-launch-client",
            common_root
            / "SteamLinuxRuntime_soldier"
            / "pressure-vessel"
            / "bin"
            / "steam-runtime-launch-client",
            common_root
            / "SteamLinuxRuntime"
            / "steam-runtime"
            / "amd64"
            / "usr"
            / "bin"
            / "steam-runtime-launch-client",
            Path.home()
            / ".steam"
            / "debian-installation"
            / "ubuntu12_32"
            / "steam-runtime"
            / "amd64"
            / "usr"
            / "bin"
            / "steam-runtime-launch-client",
        ]
    )

    seen = set()
    for candidate in candidates:
        candidate = candidate.expanduser()
        candidate_str = str(candidate)
        if candidate_str in seen:
            continue
        seen.add(candidate_str)
        if candidate.is_file():
            return candidate_str

    return None


def runtime_launch_available(
    launch_client: str,
    app_id: str,
    working_directory: Path,
    env: Dict[str, str],
) -> bool:
    """Return True if Steam exposes a per-app launcher service we can reuse."""

    probe_command = [
        launch_client,
        f"--bus-name=com.steampowered.App{app_id}",
        f"--directory={working_directory}",
        "--",
        "/usr/bin/true",
    ]
    result = subprocess.run(
        probe_command,
        env=env,
        cwd=str(working_directory),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def build_runtime_launch_command(
    launch_client: str,
    app_id: str,
    destination_prefix: Path,
    resolved_host_exe: Path,
    resolved_host_directory: Path,
) -> List[str]:
    """Build a Steam runtime client command that injects into Proton."""

    exe_argument = os.path.relpath(resolved_host_exe, resolved_host_directory)
    return [
        launch_client,
        f"--bus-name=com.steampowered.App{app_id}",
        f"--directory={resolved_host_directory}",
        f"--env=STEAM_COMPAT_DATA_PATH={destination_prefix}",
        f"--env=WINEPREFIX={destination_prefix / 'pfx'}",
        f"--env=STEAM_COMPAT_INSTALL_PATH={resolved_host_directory}",
        f"--env=SteamAppId={app_id}",
        f"--env=STEAM_COMPAT_APP_ID={app_id}",
        "--",
        "wine",
        exe_argument,
    ]


def summarize_command(cmdline: Sequence[str]) -> str:
    """Create a compact one-line process description."""

    if not cmdline:
        return "<unknown>"
    summary = " ".join(cmdline[:6])
    if len(cmdline) > 6:
        summary += " ..."
    return summary


def build_candidate(pid: int) -> Optional[ProcessCandidate]:
    """Inspect a process and decide whether it looks Proton-managed."""

    env = read_environ(pid)
    compat_data_path = env.get("STEAM_COMPAT_DATA_PATH")
    if not compat_data_path:
        return None

    cmdline = read_cmdline(pid)
    exe_hint = guess_windows_exe(cmdline)

    return ProcessCandidate(
        pid=pid,
        command=summarize_command(cmdline),
        exe_hint=exe_hint,
        compat_data_path=compat_data_path,
        proton_path=find_proton_script(env),
    )


def list_candidates() -> List[ProcessCandidate]:
    """Return all currently visible Proton-like game processes."""

    candidates = []
    for pid in iter_proc_ids():
        candidate = build_candidate(pid)
        if candidate is not None:
            candidates.append(candidate)
    return sorted(candidates, key=lambda item: item.pid)


def normalize_candidate_path(path: Optional[str]) -> Optional[str]:
    """Normalize Windows and Unix executable paths to a comparable key."""

    if not path:
        return None

    normalized = path.replace("\\", "/")
    if normalized.startswith("//?/"):
        normalized = normalized[4:]
    if len(normalized) >= 2 and normalized[1] == ":":
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    return normalized.lower() or None


def candidate_display_name(candidate: ProcessCandidate) -> str:
    """Return a friendly game name for process selection UIs."""

    if candidate.exe_hint:
        windows_name = PureWindowsPath(candidate.exe_hint).name
        if windows_name:
            return windows_name

        unix_name = Path(candidate.exe_hint).name
        if unix_name:
            return unix_name

    if candidate.command and candidate.command != "<unknown>":
        first_token = candidate.command.split()[0]
        if first_token:
            windows_name = PureWindowsPath(first_token).name
            if windows_name:
                return windows_name
            unix_name = Path(first_token).name
            if unix_name:
                return unix_name

    return f"Process {candidate.pid}"


def candidate_identity_key(candidate: ProcessCandidate) -> str:
    """Return a grouping key used to hide duplicate helper processes."""

    normalized_path = normalize_candidate_path(candidate.exe_hint)
    if normalized_path:
        return normalized_path
    return f"pid:{candidate.pid}"


def is_noise_candidate(candidate: ProcessCandidate) -> bool:
    """Return True for helper/system processes that should be hidden in the GUI."""

    return candidate_display_name(candidate).lower() in NOISE_EXECUTABLE_NAMES


def candidate_priority(candidate: ProcessCandidate) -> tuple[int, int]:
    """Score candidates so the GUI prefers the real game process."""

    score = 0
    name = candidate_display_name(candidate).lower()
    command_lower = candidate.command.lower()

    if candidate.exe_hint:
        score += 20
    if name and name not in NOISE_EXECUTABLE_NAMES:
        score += 30
    if candidate.exe_hint and PureWindowsPath(candidate.exe_hint).drive:
        score += 15
    if command_lower.startswith(("z:\\", "c:\\", "/")):
        score += 15
    if command_lower.startswith("python") or "waitforexitandrun" in command_lower:
        score -= 15
    if name in NOISE_EXECUTABLE_NAMES:
        score -= 100

    return (score, candidate.pid)


def user_facing_candidates(candidates: Sequence[ProcessCandidate]) -> List[ProcessCandidate]:
    """Collapse noisy helper processes down to the best user-facing choices."""

    picked: Dict[tuple[str, str], ProcessCandidate] = {}

    for candidate in candidates:
        if is_noise_candidate(candidate):
            continue

        key = (
            candidate.compat_data_path or "",
            candidate_identity_key(candidate),
        )
        current = picked.get(key)
        if current is None or candidate_priority(candidate) > candidate_priority(current):
            picked[key] = candidate

    if not picked:
        return list(candidates)

    return sorted(
        picked.values(),
        key=lambda item: (candidate_display_name(item).lower(), item.pid),
    )


def filtered_proton_env(source_env: Dict[str, str]) -> Dict[str, str]:
    """Extract just the Proton-related environment needed for a follow-up launch."""

    result: Dict[str, str] = {}

    for key, value in source_env.items():
        if key.startswith(IMPORTANT_ENV_PREFIXES):
            result[key] = value

    for key in SESSION_ENV_KEYS:
        if key in source_env:
            result[key] = source_env[key]
        elif key in os.environ:
            result[key] = os.environ[key]

    return result


def resolve_host_path(
    path: str,
    compat_data_path: Path,
    source_cwd: Optional[Path] = None,
) -> Optional[Path]:
    """Translate an executable path to the matching host filesystem location."""

    def resolve_relative(parts: Iterable[str]) -> Optional[Path]:
        if source_cwd is None:
            return None
        return source_cwd.joinpath(*parts).resolve()

    posix_candidate = Path(path).expanduser()
    if posix_candidate.is_absolute() or path.startswith("~"):
        return posix_candidate.resolve()
    if "/" in path and "\\" not in path:
        return resolve_relative(posix_candidate.parts)

    windows_path = PureWindowsPath(path)
    if not windows_path.drive:
        return resolve_relative(windows_path.parts)

    drive_name = windows_path.drive.rstrip(":").lower()
    drive_root = compat_data_path / "pfx" / "dosdevices" / f"{drive_name}:"
    if not drive_root.exists():
        return None

    return drive_root.resolve().joinpath(*windows_path.parts[1:]).resolve()


def copy_prefix_if_requested(source_prefix: Path, clone_prefix: Optional[Path]) -> Path:
    """Clone a Proton prefix directory if the caller requested it."""

    if clone_prefix is None:
        return source_prefix

    clone_prefix = clone_prefix.expanduser().resolve()
    source_prefix = source_prefix.expanduser().resolve()

    if clone_prefix == source_prefix:
        raise ValueError("Clone destination must be different from the source prefix.")
    if clone_prefix.is_relative_to(source_prefix):
        raise ValueError("Clone destination must not be inside the source prefix.")

    if clone_prefix.exists():
        raise ValueError(f"Clone destination already exists: {clone_prefix}")

    clone_prefix.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_prefix, clone_prefix)
    return clone_prefix


def resolve_executable(user_supplied_exe: Optional[str], source_cmdline: Sequence[str]) -> str:
    """Decide which Windows executable Proton should launch."""

    if user_supplied_exe:
        return user_supplied_exe

    guessed = guess_windows_exe(list(source_cmdline))
    if guessed:
        return guessed

    raise ValueError(
        "Could not infer the Windows executable automatically. "
        "Please rerun with --exe '/path/to/Game.exe'."
    )


def build_clone_prefix_suggestion(
    candidate: ProcessCandidate,
    base_directory: Optional[Path] = None,
) -> Path:
    """Create a friendly default clone-prefix location for the GUI."""

    if base_directory is None:
        base_directory = DEFAULT_CLONE_PREFIX_DIR

    stem = Path(candidate_display_name(candidate)).stem.lower()
    safe_stem = "".join(
        character if character.isalnum() else "-"
        for character in stem
    ).strip("-")
    if not safe_stem:
        safe_stem = f"game-{candidate.pid}"

    target = base_directory / f"{safe_stem}-second"
    if not target.exists():
        return target

    suffix = 2
    while True:
        candidate_path = base_directory / f"{safe_stem}-second-{suffix}"
        if not candidate_path.exists():
            return candidate_path
        suffix += 1


def launch_second_instance(
    pid: int,
    exe_override: Optional[str],
    clone_prefix_to: Optional[str],
    dry_run: bool,
    reporter: Optional[Callable[[str], None]] = None,
) -> int:
    """Launch a second Proton process modeled after an existing one."""

    source_env = read_environ(pid)
    if not source_env:
        raise ValueError(f"Could not read environment for PID {pid}.")

    proton_script = find_proton_script(source_env)
    if not proton_script:
        raise ValueError(
            "Could not locate Proton from the running process environment."
        )

    source_cmdline = read_cmdline(pid)
    source_cwd = read_cwd(pid)
    windows_exe = resolve_executable(exe_override, source_cmdline)

    compat_data_path = source_env.get("STEAM_COMPAT_DATA_PATH")
    if not compat_data_path:
        raise ValueError("The selected process does not expose STEAM_COMPAT_DATA_PATH.")

    source_prefix = Path(compat_data_path)
    destination_prefix = copy_prefix_if_requested(
        source_prefix=source_prefix,
        clone_prefix=Path(clone_prefix_to) if clone_prefix_to else None,
    )

    launch_env = filtered_proton_env(source_env)
    launch_env["STEAM_COMPAT_DATA_PATH"] = str(destination_prefix)

    resolved_host_exe = resolve_host_path(
        windows_exe,
        destination_prefix,
        source_cwd=source_cwd,
    )
    resolved_host_directory: Optional[Path] = None
    if resolved_host_exe is not None and resolved_host_exe.parent.is_dir():
        resolved_host_directory = resolved_host_exe.parent
    elif source_cwd is not None and source_cwd.is_dir():
        resolved_host_directory = source_cwd

    if (
        "STEAM_COMPAT_INSTALL_PATH" not in launch_env
        and resolved_host_directory is not None
    ):
        launch_env["STEAM_COMPAT_INSTALL_PATH"] = str(resolved_host_directory)

    working_directory = str(resolved_host_directory) if resolved_host_directory else None
    direct_command = [proton_script, "run", windows_exe]

    app_id = resolve_app_id(source_env, source_prefix)
    runtime_launch_client = find_runtime_launch_client(source_env, proton_script)
    runtime_command: Optional[List[str]] = None
    runtime_bus_name: Optional[str] = None
    if (
        runtime_launch_client is not None
        and app_id is not None
        and resolved_host_exe is not None
        and resolved_host_directory is not None
    ):
        runtime_bus_name = f"com.steampowered.App{app_id}"
        runtime_command = build_runtime_launch_command(
            launch_client=runtime_launch_client,
            app_id=app_id,
            destination_prefix=destination_prefix,
            resolved_host_exe=resolved_host_exe,
            resolved_host_directory=resolved_host_directory,
        )

    emit_message(f"Using source PID: {pid}", reporter)
    emit_message(f"Using Proton: {proton_script}", reporter)
    emit_message(f"Using compatdata: {destination_prefix}", reporter)
    emit_message(f"Launching executable: {windows_exe}", reporter)
    if resolved_host_exe is not None:
        emit_message(f"Resolved host executable: {resolved_host_exe}", reporter)
    emit_message(
        f"Working directory: {working_directory or '<inherit current directory>'}",
        reporter,
    )
    if runtime_launch_client is not None:
        emit_message(f"Steam runtime launch client: {runtime_launch_client}", reporter)
    if runtime_bus_name is not None:
        emit_message(f"Runtime bus name: {runtime_bus_name}", reporter)
    if runtime_command is not None:
        emit_message(f"Preferred command: {' '.join(runtime_command)}", reporter)
        emit_message(f"Fallback command: {' '.join(direct_command)}", reporter)
    else:
        emit_message(f"Command: {' '.join(direct_command)}", reporter)

    if dry_run:
        emit_message("Dry run requested; not starting a new process.", reporter)
        return 0

    if (
        runtime_launch_client is not None
        and app_id is not None
        and resolved_host_directory is not None
        and runtime_command is not None
        and runtime_launch_available(
            launch_client=runtime_launch_client,
            app_id=app_id,
            working_directory=resolved_host_directory,
            env=launch_env,
        )
    ):
        process = subprocess.Popen(
            runtime_command,
            env=launch_env,
            cwd=working_directory,
            start_new_session=True,
        )
        emit_message("Launch mode: Steam runtime client", reporter)
        emit_message(f"Started second instance with PID {process.pid}", reporter)
        return 0

    if runtime_command is not None:
        emit_message(
            "Steam's per-app launcher service is not available, so this run is "
            "falling back to direct Proton. That fallback can still show the "
            "Fontconfig and ALSA warnings you saw.",
            reporter,
        )
        if source_env.get("STEAM_COMPAT_LAUNCHER_SERVICE") != "proton":
            emit_message(
                "Hint: set the Steam shortcut launch options to "
                "STEAM_COMPAT_LAUNCHER_SERVICE=proton %command%, launch the "
                "first copy from Steam again, then rerun this script.",
                reporter,
            )

    process = subprocess.Popen(
        direct_command,
        env=launch_env,
        cwd=working_directory,
        start_new_session=True,
    )

    emit_message("Launch mode: direct Proton fallback", reporter)
    emit_message(f"Started second instance with PID {process.pid}", reporter)
    return 0
