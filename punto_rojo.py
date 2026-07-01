from __future__ import annotations

import os
import sys

# Agregar la carpeta 'src' al sys.path de manera dinámica para que funcione
# sin requerir entornos uv o configuración manual de PYTHONPATH.
base_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(base_dir, "src")
if os.path.exists(src_dir) and src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from hakunamatata.capture import ocultar_region
from hakunamatata.detection import EstadoDeteccion, actualizar_estado
from hakunamatata.ui import main

__all__ = ["EstadoDeteccion", "actualizar_estado", "ocultar_region"]


if __name__ == "__main__":
    try:
        from hakunamatata.gemini import crear_cliente

        cliente = crear_cliente()
    except ImportError:
        cliente = None
    except (KeyboardInterrupt, EOFError):
        print("\nConfiguración cancelada.")
        cliente = None

    main(cliente)
