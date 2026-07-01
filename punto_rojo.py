from __future__ import annotations

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
