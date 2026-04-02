"""CLI and application entry wiring."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .backend import launch_second_instance, list_candidates
from .gui import launch_gui
from .host import maybe_reexec_on_host


def cmd_list(_: argparse.Namespace) -> int:
    """Handle the list command."""

    candidates = list_candidates()
    if not candidates:
        print(
            "No Proton game processes found.\n"
            "Start the first instance from Steam, then try again."
        )
        return 1

    for candidate in candidates:
        print(f"PID: {candidate.pid}")
        print(f"Command: {candidate.command}")
        print(f"Compatdata: {candidate.compat_data_path or '<missing>'}")
        print(f"Proton: {candidate.proton_path or '<missing>'}")
        print(f"Exe hint: {candidate.exe_hint or '<unknown>'}")
        print()

    return 0


def cmd_launch(args: argparse.Namespace) -> int:
    """Handle the launch command."""

    return launch_second_instance(
        pid=args.pid,
        exe_override=args.exe,
        clone_prefix_to=args.clone_prefix_to,
        dry_run=args.dry_run,
    )


def cmd_gui(_: argparse.Namespace) -> int:
    """Handle the gui command."""

    return launch_gui()


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level CLI argument parser."""

    parser = argparse.ArgumentParser(
        prog="proton-dupe-launcher",
        description=(
            "Launch a second copy of a non-Steam Proton game by reusing "
            "the environment from a running first instance."
        )
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=False)

    list_parser = subparsers.add_parser(
        "list",
        help="List running Proton game processes that can be used as a source.",
    )
    list_parser.set_defaults(func=cmd_list)

    launch_parser = subparsers.add_parser(
        "launch",
        help="Launch a second instance based on the environment of a running PID.",
    )
    launch_parser.add_argument(
        "--pid",
        type=int,
        required=True,
        help="PID of the already-running Proton game process.",
    )
    launch_parser.add_argument(
        "--exe",
        help=(
            "Windows executable to launch. Optional if the script can infer it "
            "from the running process."
        ),
    )
    launch_parser.add_argument(
        "--clone-prefix-to",
        help=(
            "Optional new compatdata directory to create by copying the source "
            "prefix before launch."
        ),
    )
    launch_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the detected launch details without starting the second copy.",
    )
    launch_parser.set_defaults(func=cmd_launch)

    gui_parser = subparsers.add_parser(
        "gui",
        help="Open the desktop app.",
    )
    gui_parser.set_defaults(func=cmd_gui)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Application entry point with friendly error handling."""

    raw_argv = list(argv if argv is not None else sys.argv[1:])
    parser = build_parser()
    args = parser.parse_args(raw_argv)
    command_name = args.command or "gui"

    host_exit_code = maybe_reexec_on_host(raw_argv, command_name)
    if host_exit_code is not None:
        return host_exit_code

    try:
        if args.command is None:
            return launch_gui()
        return args.func(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
