from __future__ import annotations

import sys


def main(cliente=None) -> None:
    if sys.platform == "darwin":
        from .macos import ejecutar

        ejecutar(cliente)
        return

    if sys.platform.startswith("win"):
        from .windows import ejecutar

        ejecutar(cliente)
        return

    raise SystemExit("Plataforma no soportada")
