"""Host re-exec helpers for Flatpak-based environments."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Sequence

from .backend import SESSION_ENV_KEYS


HOST_EXEC_ENV = "PROTON_DUPE_LAUNCHER_HOST_EXEC"


def running_inside_flatpak() -> bool:
    """Return True when the launcher is running inside a Flatpak sandbox."""

    return Path("/.flatpak-info").exists() or "FLATPAK_ID" in os.environ


def command_requires_host_access(command_name: str) -> bool:
    """Return True for commands that need the real host process list."""

    return command_name in {"gui", "list", "launch"}


def maybe_reexec_on_host(argv: Sequence[str], command_name: str) -> Optional[int]:
    """Re-run the launcher on the host when started from a Flatpak sandbox."""

    if not command_requires_host_access(command_name):
        return None
    if os.environ.get(HOST_EXEC_ENV) == "1":
        return None
    if not running_inside_flatpak():
        return None

    flatpak_spawn = shutil.which("flatpak-spawn")
    if flatpak_spawn is None:
        return None

    launcher_module = "protondupe_launcher"
    env = os.environ.copy()
    env[HOST_EXEC_ENV] = "1"

    command = [
        flatpak_spawn,
        "--host",
        f"--directory={os.getcwd()}",
    ]
    for key in SESSION_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            command.append(f"--env={key}={value}")
    command.extend(
        [
            f"--env={HOST_EXEC_ENV}=1",
            "python3",
            "-m",
            launcher_module,
            *argv,
        ]
    )

    return subprocess.run(command, env=env, check=False).returncode
