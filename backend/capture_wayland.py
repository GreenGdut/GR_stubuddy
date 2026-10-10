from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.introspection import Node


PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
SCREENSHOT_INTERFACE = "org.freedesktop.portal.Screenshot"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"
DEBUG_LOG_FILE = Path("/tmp/stubuddy/log")
PORTAL_INTROSPECTION = Node.parse(
    """
    <node>
      <interface name="org.freedesktop.portal.Screenshot">
        <method name="Screenshot">
          <arg type="s" direction="in"/>
          <arg type="a{sv}" direction="in"/>
          <arg type="o" direction="out"/>
        </method>
      </interface>
    </node>
    """
)
REQUEST_INTROSPECTION = Node.parse(
    """
    <node>
      <interface name="org.freedesktop.portal.Request">
        <signal name="Response">
          <arg type="u"/>
          <arg type="a{sv}"/>
        </signal>
      </interface>
    </node>
    """
)


def _write_debug(message: str) -> None:
    try:
        DEBUG_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        with DEBUG_LOG_FILE.open("a", encoding="utf-8") as log_file:
            log_file.write(f"[{timestamp}] [python] Wayland 截图: {message}\n")
    except OSError:
        pass


def _pictures_directory() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    user_dirs = config_home / "user-dirs.dirs"
    try:
        for line in user_dirs.read_text(encoding="utf-8").splitlines():
            if line.startswith("XDG_PICTURES_DIR="):
                value = line.split("=", 1)[1].strip().strip('"')
                return Path(value.replace("$HOME", str(Path.home()), 1))
    except OSError:
        pass
    return Path.home() / "Pictures"


def _system_screenshot_files() -> dict[Path, int]:
    screenshots_directory = _pictures_directory() / "Screenshots"
    try:
        return {
            path: path.stat().st_mtime_ns
            for path in screenshots_directory.glob("*.png")
            if path.is_file()
        }
    except OSError:
        return {}


def _new_system_screenshot(previous_files: dict[Path, int]) -> Path | None:
    current_files = _system_screenshot_files()
    changed_files = [
        path
        for path, modified_time in current_files.items()
        if previous_files.get(path) != modified_time
    ]
    return max(changed_files, key=lambda path: current_files[path], default=None)


async def _request_screenshot() -> Path | None:
    _write_debug("开始连接 Screenshot Portal")
    previous_system_screenshots = _system_screenshot_files()
    bus = await MessageBus().connect()
    try:
        if not bus.unique_name:
            raise RuntimeError("无法获取 Wayland D-Bus 会话名称")
        token = f"stubuddy_{uuid.uuid4().hex}"
        sender = bus.unique_name.lstrip(":").replace(".", "_")
        expected_request_path = (
            f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
        )
        response_future: asyncio.Future[tuple[int, dict[str, Variant]]] = (
            asyncio.get_running_loop().create_future()
        )

        request_object = bus.get_proxy_object(
            PORTAL_BUS_NAME, expected_request_path, REQUEST_INTROSPECTION
        )
        request_interface = request_object.get_interface(REQUEST_INTERFACE)

        def on_response(response: int, results: dict[str, Variant]) -> None:
            if not response_future.done():
                response_future.set_result((response, results))

        request_interface.on_response(on_response)

        portal_object = bus.get_proxy_object(
            PORTAL_BUS_NAME, PORTAL_OBJECT_PATH, PORTAL_INTROSPECTION
        )
        screenshot_interface = portal_object.get_interface(SCREENSHOT_INTERFACE)
        request_path = await screenshot_interface.call_screenshot(
            "",
            {
                "handle_token": Variant("s", token),
                "interactive": Variant("b", True),
            },
        )
        if request_path != expected_request_path:
            raise RuntimeError("Wayland 截图门户返回了非预期请求路径")
        _write_debug(f"已创建请求 {request_path}，等待用户操作")

        try:
            response, results = await asyncio.wait_for(response_future, timeout=300)
        except TimeoutError as error:
            raise RuntimeError("等待 Wayland 截图门户响应超时") from error
        _write_debug(f"门户响应码 {response}，字段 {sorted(results)}")
        if response == 1:
            _write_debug("用户取消截图")
            return None
        if "uri" in results:
            uri = str(results["uri"].value)
            _write_debug(f"门户返回图像 {uri}")
            parsed_uri = urlparse(uri)
            if parsed_uri.scheme != "file":
                raise RuntimeError("Wayland 截图门户返回了不支持的图像地址")
            return Path(unquote(parsed_uri.path))

        fallback_image = _new_system_screenshot(previous_system_screenshots)
        if fallback_image is not None:
            _write_debug(f"门户未返回 URI，使用系统截图 {fallback_image}")
            return fallback_image
        raise RuntimeError("Wayland 截图门户未返回图像")
    finally:
        bus.disconnect()


def capture_region(output_path: Path) -> bool:
    portal_image = asyncio.run(_request_screenshot())
    if portal_image is None:
        return False
    if not portal_image.is_file():
        raise RuntimeError("Wayland 截图门户生成的图像不存在")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(portal_image, output_path)
    _write_debug(f"图像已保存到 {output_path}")
    return True
