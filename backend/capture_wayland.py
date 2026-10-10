from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from dbus_next import Variant
from dbus_next.aio import MessageBus


PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
SCREENSHOT_INTERFACE = "org.freedesktop.portal.Screenshot"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"


async def _request_screenshot() -> Path | None:
    bus = await MessageBus().connect()
    try:
        portal_introspection = await bus.introspect(PORTAL_BUS_NAME, PORTAL_OBJECT_PATH)
        portal_object = bus.get_proxy_object(
            PORTAL_BUS_NAME, PORTAL_OBJECT_PATH, portal_introspection
        )
        screenshot_interface = portal_object.get_interface(SCREENSHOT_INTERFACE)
        request_path = await screenshot_interface.call_screenshot(
            "",
            {
                "handle_token": Variant("s", f"stubuddy_{uuid.uuid4().hex}"),
                "interactive": Variant("b", True),
            },
        )

        request_introspection = await bus.introspect(PORTAL_BUS_NAME, request_path)
        request_object = bus.get_proxy_object(
            PORTAL_BUS_NAME, request_path, request_introspection
        )
        request_interface = request_object.get_interface(REQUEST_INTERFACE)
        response_future: asyncio.Future[tuple[int, dict[str, Variant]]] = (
            asyncio.get_running_loop().create_future()
        )

        def on_response(response: int, results: dict[str, Variant]) -> None:
            if not response_future.done():
                response_future.set_result((response, results))

        request_interface.on_response(on_response)
        response, results = await response_future
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
