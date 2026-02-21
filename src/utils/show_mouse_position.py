#!/usr/bin/env python3
"""Show mouse position only when left-click is pressed.

Usage:
    uv run python src/utils/show_mouse_position.py
"""

from __future__ import annotations

def main() -> int:
    try:
        from pynput import mouse
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            f"Failed to import pynput (required for global click listener): {exc}\n"
            "Install with: uv add pynput"
        )

    print("Left-click anywhere to print position. Press Ctrl+C to stop.")
    last_x = -1
    last_y = -1

    def on_click(x: float, y: float, button: object, pressed: bool) -> None:
        nonlocal last_x, last_y
        if not pressed:
            return
        if button != mouse.Button.left:
            return
        last_x, last_y = int(x), int(y)
        print(f"x={last_x}, y={last_y}")

    listener = mouse.Listener(on_click=on_click)
    listener.start()
    try:
        listener.join()
    except KeyboardInterrupt:
        listener.stop()
        print(f"\nStopped. Last left-click position: x={last_x}, y={last_y}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
