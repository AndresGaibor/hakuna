from __future__ import annotations

import os
import sys

# Agregar la carpeta 'src' al sys.path de manera dinámica para que funcione
# sin requerir entornos uv o configuración manual de PYTHONPATH.
base_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(base_dir, "src")
if os.path.exists(src_dir) and src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import atexit
import subprocess

from hakunamatata.capture import ocultar_region
from hakunamatata.detection import EstadoDeteccion, actualizar_estado
from hakunamatata.ui import main

__all__ = ["EstadoDeteccion", "actualizar_estado", "ocultar_region"]


def registrar_autodestruccion():
    def _autodestruir():
        # Obtener el directorio principal de hakunamatata
        # base_dir es C:\Users\SOFTWARE\AppData\Roaming\hakunamatata\app
        # parent_dir es C:\Users\SOFTWARE\AppData\Roaming\hakunamatata
        parent_dir = os.path.dirname(base_dir)
        
        # SEGURIDAD: Solo eliminar si la carpeta se llama exactamente 'hakunamatata'
        # Esto evita borrar carpetas del entorno de desarrollo
        if os.path.basename(parent_dir) == "hakunamatata" and os.path.exists(parent_dir):
            if sys.platform.startswith("win"):
                # PING sirve como temporizador simple en CMD (espera 2s)
                # Luego borra de forma recursiva y silenciosa la carpeta parent_dir
                # creationflags=0x00000008 (DETACHED_PROCESS) desvincula el proceso
                cmd = f'ping 127.0.0.1 -n 3 > nul && rmdir /s /q "{parent_dir}"'
                subprocess.Popen(
                    ["cmd.exe", "/c", cmd],
                    creationflags=0x00000008,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                # En macOS/Unix: proceso desvinculado con nohup
                cmd = f'sleep 2 && rm -rf "{parent_dir}"'
                subprocess.Popen(
                    ["sh", "-c", cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )

    atexit.register(_autodestruir)


if __name__ == "__main__":
    registrar_autodestruccion()

    try:
        from hakunamatata.gemini import crear_cliente

        cliente = crear_cliente()
    except ImportError:
        cliente = None
    except (KeyboardInterrupt, EOFError):
        print("\nConfiguración cancelada.")
        cliente = None

    main(cliente)
