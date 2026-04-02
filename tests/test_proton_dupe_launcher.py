import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from protondupe_launcher import backend as launcher


class ResolveAppIdTests(unittest.TestCase):
    def test_ignores_ambient_shell_app_id_when_source_process_lacks_one(self) -> None:
        compat_data_path = Path("/tmp/123456")

        with mock.patch.dict(os.environ, {"SteamAppId": "999999"}, clear=False):
            app_id = launcher.resolve_app_id({}, compat_data_path)

        self.assertEqual(app_id, "123456")

    def test_ignores_zero_app_ids_and_falls_back_to_compatdata_name(self) -> None:
        compat_data_path = Path("/tmp/3332790986")

        app_id = launcher.resolve_app_id(
            {
                "STEAM_COMPAT_APP_ID": "0",
                "SteamAppId": "0",
            },
            compat_data_path,
        )

        self.assertEqual(app_id, "3332790986")


class CopyPrefixTests(unittest.TestCase):
    def test_rejects_clone_destination_inside_source_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_prefix = Path(temp_dir) / "compatdata" / "1234"
            source_prefix.mkdir(parents=True)
            (source_prefix / "version").write_text("1", encoding="utf-8")

            clone_prefix = source_prefix / "clone"

            with self.assertRaisesRegex(ValueError, "inside the source prefix"):
                launcher.copy_prefix_if_requested(source_prefix, clone_prefix)


class ResolveHostPathTests(unittest.TestCase):
    def test_resolves_relative_executable_against_source_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            compat_data_path = temp_path / "compatdata" / "1234"
            source_cwd = temp_path / "Games" / "Example"
            source_cwd.mkdir(parents=True)
            exe_path = source_cwd / "Game.exe"
            exe_path.write_text("", encoding="utf-8")

            resolved = launcher.resolve_host_path(
                "Game.exe",
                compat_data_path,
                source_cwd=source_cwd,
            )

        self.assertEqual(resolved, exe_path.resolve())

    def test_resolves_relative_posix_path_against_source_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            compat_data_path = temp_path / "compatdata" / "1234"
            source_cwd = temp_path / "Games" / "Example"
            source_cwd.mkdir(parents=True)
            exe_path = source_cwd / "bin" / "Game.exe"
            exe_path.parent.mkdir(parents=True)
            exe_path.write_text("", encoding="utf-8")

            resolved = launcher.resolve_host_path(
                "./bin/Game.exe",
                compat_data_path,
                source_cwd=source_cwd,
            )

        self.assertEqual(resolved, exe_path.resolve())


class UserFacingCandidateTests(unittest.TestCase):
    def test_prefers_real_game_process_over_wrapper_and_filters_noise(self) -> None:
        compat_path = "/tmp/compatdata/1234"
        proton_path = "/tmp/proton"
        wrapper = launcher.ProcessCandidate(
            pid=100,
            command="python3 proton waitforexitandrun /games/WowExt.exe",
            exe_hint="/home/dorian/Games/Synastria WoW/WowExt.exe",
            compat_data_path=compat_path,
            proton_path=proton_path,
        )
        real_game = launcher.ProcessCandidate(
            pid=200,
            command=r"Z:\home\dorian\Games\Synastria WoW\WowExt.exe",
            exe_hint=r"Z:\home\dorian\Games\Synastria WoW\WowExt.exe",
            compat_data_path=compat_path,
            proton_path=proton_path,
        )
        noise = launcher.ProcessCandidate(
            pid=300,
            command=r"C:\windows\system32\services.exe",
            exe_hint=r"C:\windows\system32\services.exe",
            compat_data_path=compat_path,
            proton_path=proton_path,
        )

        candidates = launcher.user_facing_candidates([wrapper, real_game, noise])

        self.assertEqual(candidates, [real_game])


class CloneSuggestionTests(unittest.TestCase):
    def test_builds_human_friendly_clone_prefix_path(self) -> None:
        candidate = launcher.ProcessCandidate(
            pid=100,
            command=r"Z:\Games\Wow Ext.exe",
            exe_hint=r"Z:\Games\Wow Ext.exe",
            compat_data_path="/tmp/compatdata/1234",
            proton_path="/tmp/proton",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            suggestion = launcher.build_clone_prefix_suggestion(
                candidate,
                base_directory=Path(temp_dir),
            )

        self.assertEqual(suggestion.name, "wow-ext-second")

    def test_adds_numeric_suffix_when_suggested_clone_path_exists(self) -> None:
        candidate = launcher.ProcessCandidate(
            pid=100,
            command=r"Z:\Games\WowExt.exe",
            exe_hint=r"Z:\Games\WowExt.exe",
            compat_data_path="/tmp/compatdata/1234",
            proton_path="/tmp/proton",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            base_directory = Path(temp_dir)
            (base_directory / "wowext-second").mkdir()
            suggestion = launcher.build_clone_prefix_suggestion(
                candidate,
                base_directory=base_directory,
            )

        self.assertEqual(suggestion.name, "wowext-second-2")


if __name__ == "__main__":
    unittest.main()
