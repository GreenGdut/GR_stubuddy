from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.introspection import Node


PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
SCREENSHOT_INTERFACE = "org.freedesktop.portal.Screenshot"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"
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


async def _request_screenshot() -> Path | None:
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

        try:
            response, results = await asyncio.wait_for(response_future, timeout=300)
        except TimeoutError as error:
            raise RuntimeError("等待 Wayland 截图门户响应超时") from error
        if response == 1:
            return None
        if response != 0 or "uri" not in results:
            raise RuntimeError("Wayland 截图门户未返回图像")

        uri = str(results["uri"].value)
        parsed_uri = urlparse(uri)
        if parsed_uri.scheme != "file":
            raise RuntimeError("Wayland 截图门户返回了不支持的图像地址")
        return Path(unquote(parsed_uri.path))
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
    return True
