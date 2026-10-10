from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from backend.workspace import (
    WorkspaceError,
    create_or_recover_workspace,
    create_project,
    get_workspace_state,
    next_screenshot_path,
)


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _capture(project_folder: Path) -> dict[str, Any]:
    output_path = next_screenshot_path(project_folder)

    if sys.platform == "win32":
        from backend.capture_windows import capture_region
    elif sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY"):
        from backend.capture_wayland import capture_region
    else:
        raise WorkspaceError(
            "UNSUPPORTED_CAPTURE",
            "当前截图后端仅支持 Windows 10/11 和 Linux Wayland",
        )

    captured = capture_region(output_path)
    if not captured:
        return {"ok": True, "status": "cancelled"}
    return {"ok": True, "status": "captured", "path": str(output_path.resolve())}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stubuddy-backend")
    subparsers = parser.add_subparsers(dest="command", required=True)

    state_parser = subparsers.add_parser("state")
    state_parser.add_argument("--target", type=Path)

    workspace_parser = subparsers.add_parser("create-workspace")
    workspace_parser.add_argument("--parent", required=True, type=Path)

    project_parser = subparsers.add_parser("create-project")
    project_parser.add_argument("--target", required=True, type=Path)

    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--project", required=True, type=Path)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        if args.command == "state":
            result: dict[str, Any] = {
                "ok": True,
                "state": get_workspace_state(args.target),
            }
        elif args.command == "create-workspace":
            result = {
                "ok": True,
                "state": create_or_recover_workspace(args.parent),
            }
        elif args.command == "create-project":
            result = {"ok": True, "state": create_project(args.target)}
        else:
            result = _capture(args.project)
        _emit(result)
        return 0
    except WorkspaceError as error:
        _emit({"ok": False, "code": error.code, "message": str(error)})
    except Exception as error:
        _emit({"ok": False, "code": "BACKEND_ERROR", "message": str(error)})
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
