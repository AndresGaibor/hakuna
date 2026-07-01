from __future__ import annotations

import sys


def obtener_posicion_mouse() -> tuple[float, float]:
    if sys.platform == "darwin":
        from AppKit import NSEvent

        punto = NSEvent.mouseLocation()
        return float(punto.x), float(punto.y)

    if sys.platform.startswith("win"):
        import ctypes
        from ctypes import wintypes

        punto = wintypes.POINT()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(punto)):
            raise OSError("No se pudo leer la posición del mouse")
        return float(punto.x), float(punto.y)

    raise SystemExit("Plataforma no soportada")
