from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus


PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
SCREENSHOT_INTERFACE = "org.freedesktop.portal.Screenshot"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"
DBUS_BUS_NAME = "org.freedesktop.DBus"
DBUS_OBJECT_PATH = "/org/freedesktop/DBus"
DBUS_INTERFACE = "org.freedesktop.DBus"


def _method_result(reply: Message | None, operation: str) -> list[object]:
    if reply is None:
        raise RuntimeError(f"{operation}未返回结果")
    if reply.message_type == MessageType.ERROR:
        detail = str(reply.body[0]) if reply.body else reply.error_name
        raise RuntimeError(f"{operation}失败: {detail}")
    if reply.message_type != MessageType.METHOD_RETURN:
        raise RuntimeError(f"{operation}未返回有效结果")
    return reply.body


async def _request_screenshot() -> Path | None:
    bus = await MessageBus().connect()
    try:
        response_future: asyncio.Future[tuple[int, dict[str, Variant]]] = (
            asyncio.get_running_loop().create_future()
        )
        request_path: str | None = None
        pending_responses: dict[str, tuple[int, dict[str, Variant]]] = {}

        def on_message(message: Message) -> None:
            if (
                message.message_type != MessageType.SIGNAL
                or message.interface != REQUEST_INTERFACE
                or message.member != "Response"
                or message.path is None
                or len(message.body) != 2
            ):
                return
            response = (int(message.body[0]), message.body[1])
            if message.path == request_path and not response_future.done():
                response_future.set_result(response)
            else:
                pending_responses[message.path] = response

        bus.add_message_handler(on_message)
        match_reply = await bus.call(
            Message(
                destination=DBUS_BUS_NAME,
                path=DBUS_OBJECT_PATH,
                interface=DBUS_INTERFACE,
                member="AddMatch",
                signature="s",
                body=[
                    "type='signal',interface='org.freedesktop.portal.Request',"
                    "member='Response'"
                ],
            )
        )
        _method_result(match_reply, "监听 Wayland 截图门户")

        screenshot_reply = await bus.call(
            Message(
                destination=PORTAL_BUS_NAME,
                path=PORTAL_OBJECT_PATH,
                interface=SCREENSHOT_INTERFACE,
                member="Screenshot",
                signature="sa{sv}",
                body=[
                    "",
                    {
                        "handle_token": Variant(
                            "s", f"stubuddy_{uuid.uuid4().hex}"
                        ),
                        "interactive": Variant("b", True),
                    },
                ],
            )
        )
        screenshot_result = _method_result(screenshot_reply, "调用 Wayland 截图门户")
        if len(screenshot_result) != 1 or not isinstance(screenshot_result[0], str):
            raise RuntimeError("Wayland 截图门户返回了无效请求路径")
        request_path = screenshot_result[0]
        if request_path in pending_responses:
            response_future.set_result(pending_responses[request_path])
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
