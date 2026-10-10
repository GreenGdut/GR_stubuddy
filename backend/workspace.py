from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict


TARGET_FOLDER_NAME = "Target_Stubuddy"
PROJECT_LIMIT = 999
PROJECT_PATTERN = re.compile(r"^Project(\d{3})$")
SCREENSHOT_PATTERN = re.compile(r"^input_(\d+)\.png$", re.IGNORECASE)


class WorkspaceState(TypedDict):
    targetFolder: str | None
    currentProject: str | None


class WorkspaceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _numbered_directories(target_folder: Path) -> list[tuple[int, Path]]:
    if not target_folder.is_dir():
        return []

    projects: list[tuple[int, Path]] = []
    for entry in target_folder.iterdir():
        match = PROJECT_PATTERN.fullmatch(entry.name)
        if entry.is_dir() and match:
            projects.append((int(match.group(1)), entry))
    return projects


def get_workspace_state(target_folder: Path | None) -> WorkspaceState:
    if target_folder is None or not target_folder.is_dir():
        return {"targetFolder": None, "currentProject": None}

    projects = _numbered_directories(target_folder)
    current_project = max(projects, default=None, key=lambda item: item[0])
    return {
        "targetFolder": str(target_folder.resolve()),
        "currentProject": str(current_project[1].resolve()) if current_project else None,
    }


def create_or_recover_workspace(parent_folder: Path) -> WorkspaceState:
    if not parent_folder.is_dir():
        raise WorkspaceError("INVALID_PARENT", "选择的位置不是有效文件夹")

    target_folder = (
        parent_folder
        if parent_folder.name == TARGET_FOLDER_NAME
        else parent_folder / TARGET_FOLDER_NAME
    )
    target_folder.mkdir(exist_ok=True)
    state = get_workspace_state(target_folder)
    if state["currentProject"] is None:
        return create_project(target_folder)
    return state


def create_project(target_folder: Path) -> WorkspaceState:
    if not target_folder.is_dir():
        raise WorkspaceError("TARGET_NOT_FOUND", "目标文件夹不存在，请重新创建或恢复工程")

    projects = _numbered_directories(target_folder)
    next_number = max((number for number, _ in projects), default=0) + 1
    if next_number > PROJECT_LIMIT:
        raise WorkspaceError("PROJECT_LIMIT", "工程编号已达到 Project999")

    project_folder = target_folder / f"Project{next_number:03d}"
    project_folder.mkdir()
    return get_workspace_state(target_folder)


def next_screenshot_path(project_folder: Path) -> Path:
    if not project_folder.is_dir() or not PROJECT_PATTERN.fullmatch(project_folder.name):
        raise WorkspaceError("PROJECT_NOT_FOUND", "当前工程文件夹不存在")

    numbers: list[int] = []
    for entry in project_folder.iterdir():
        match = SCREENSHOT_PATTERN.fullmatch(entry.name)
        if entry.is_file() and match:
            numbers.append(int(match.group(1)))

    return project_folder / f"input_{max(numbers, default=0) + 1:03d}.png"
