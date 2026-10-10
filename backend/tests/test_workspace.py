from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.workspace import (
    WorkspaceError,
    create_or_recover_workspace,
    create_project,
    get_workspace_state,
    next_screenshot_path,
)


class WorkspaceTests(TestCase):
    def test_creates_initial_workspace(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            state = create_or_recover_workspace(Path(temporary_directory))

            self.assertEqual(Path(state["targetFolder"]).name, "Target_Stubuddy")
            self.assertEqual(Path(state["currentProject"]).name, "Project001")

    def test_recovers_latest_project_and_does_not_fill_gaps(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "Target_Stubuddy"
            (target / "Project001").mkdir(parents=True)
            (target / "Project003").mkdir()
            (target / "ProjectABC").mkdir()

            recovered = get_workspace_state(target)
            created = create_project(target)

            self.assertEqual(Path(recovered["currentProject"]).name, "Project003")
            self.assertEqual(Path(created["currentProject"]).name, "Project004")

    def test_accepts_existing_target_folder_as_recovery_selection(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "Target_Stubuddy"
            (target / "Project007").mkdir(parents=True)

            state = create_or_recover_workspace(target)

            self.assertEqual(Path(state["targetFolder"]), target.resolve())
            self.assertEqual(Path(state["currentProject"]).name, "Project007")
            self.assertFalse((target / "Target_Stubuddy").exists())

    def test_stops_after_project_999(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "Target_Stubuddy"
            (target / "Project999").mkdir(parents=True)

            with self.assertRaises(WorkspaceError) as context:
                create_project(target)

            self.assertEqual(context.exception.code, "PROJECT_LIMIT")

    def test_screenshot_number_uses_highest_existing_number(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory) / "Project008"
            project.mkdir()
            (project / "input_001.png").touch()
            (project / "input_003.png").touch()
            (project / "input_notes.png").touch()

            self.assertEqual(next_screenshot_path(project).name, "input_004.png")
