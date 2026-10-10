from __future__ import annotations

import ctypes
from pathlib import Path
from tkinter import Canvas, Tk

import mss
from PIL import Image, ImageEnhance, ImageTk


def _enable_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def capture_region(output_path: Path) -> bool:
    _enable_dpi_awareness()

    with mss.mss() as screen_capture:
        monitor = screen_capture.monitors[0]
        shot = screen_capture.grab(monitor)
        screenshot = Image.frombytes("RGB", shot.size, shot.rgb)

    root = Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.geometry(
        f"{monitor['width']}x{monitor['height']}"
        f"{monitor['left']:+d}{monitor['top']:+d}"
    )

    canvas = Canvas(root, highlightthickness=0, cursor="crosshair")
    canvas.pack(fill="both", expand=True)
    dimmed = ImageEnhance.Brightness(screenshot).enhance(0.58)
    background = ImageTk.PhotoImage(dimmed)
    canvas.create_image(0, 0, image=background, anchor="nw")

    start: tuple[int, int] | None = None
    rectangle: int | None = None
    selection: tuple[int, int, int, int] | None = None

    def begin(event: object) -> None:
        nonlocal start, rectangle
        x, y = int(event.x), int(event.y)  # type: ignore[attr-defined]
        start = (x, y)
        rectangle = canvas.create_rectangle(x, y, x, y, outline="#d8202f", width=2)

    def drag(event: object) -> None:
        if start is None or rectangle is None:
            return
        canvas.coords(rectangle, start[0], start[1], event.x, event.y)  # type: ignore[attr-defined]

    def finish(event: object) -> None:
        nonlocal selection
        if start is None:
            return
        end_x, end_y = int(event.x), int(event.y)  # type: ignore[attr-defined]
        left, right = sorted((start[0], end_x))
        top, bottom = sorted((start[1], end_y))
        if right - left >= 2 and bottom - top >= 2:
            selection = (left, top, right, bottom)
        root.destroy()

    canvas.bind("<ButtonPress-1>", begin)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<ButtonRelease-1>", finish)
    root.bind("<Escape>", lambda _event: root.destroy())
    root.focus_force()
    root.mainloop()

    if selection is None:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    screenshot.crop(selection).save(output_path, "PNG")
    return True
