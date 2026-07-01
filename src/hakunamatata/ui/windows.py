from __future__ import annotations

import os
import sys
import threading
import time
import traceback
import tkinter as tk

from hakunamatata.capture import capturar_a_png_bytes
from hakunamatata.hud import log_hud
from hakunamatata.mouse import obtener_posicion_mouse


def ejecutar(cliente=None) -> None:
    root = tk.Tk()
    ancho = root.winfo_screenwidth()
    alto = root.winfo_screenheight()

    pendiente_gemini = False
    _necesita_captura = False
    visible = False

    color_transparente = "magenta"
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-disabled", True)
    root.configure(bg=color_transparente)
    root.geometry(f"{ancho}x{alto}+0+0")
    root.wm_attributes("-transparentcolor", color_transparente)

    canvas = tk.Canvas(root, bg=color_transparente, highlightthickness=0, borderwidth=0)
    canvas.pack(fill="both", expand=True)

    text_id = None

    def actualizar_interfaz(texto):
        """Actualiza el texto en pantalla. Se ejecuta de forma segura en el hilo principal."""
        nonlocal text_id
        if text_id is not None:
            canvas.delete(text_id)
            text_id = None
        if texto:
            # Dibujar la letra de la opción en negro extremadamente semitranslúcido en la esquina inferior izquierda
            # Margen de 35px de los bordes. Usamos un gris muy claro (#C8C8C8) para emular negro al 16% de opacidad.
            text_id = canvas.create_text(
                35,
                alto - 35,
                text=texto,
                font=("Arial", 10, "bold"),
                fill="#C8C8C8",
                anchor="sw",
            )

    def tick():
        nonlocal pendiente_gemini, _necesita_captura, visible

        _, mouse_y = obtener_posicion_mouse()
        from hakunamatata.overlay import debe_mostrarse_circulo

        is_top = debe_mostrarse_circulo(mouse_y, alto, origen_y_arriba=True)

        # ── Detectar transiciones de visibilidad ───────────────────────────────
        if is_top != visible:
            visible = is_top
            log_hud(f"Mouse {'en TOP ✓' if visible else 'fuera de TOP ✗'} (y={int(mouse_y)})")
            if visible:
                # Entrando a TOP: limpiar pantalla
                actualizar_interfaz("")
                _necesita_captura = True
            else:
                # Saliendo de TOP: limpiar pantalla de inmediato
                actualizar_interfaz("")
                if not pendiente_gemini:
                    _necesita_captura = False

        if not visible:
            root.after(300, tick)
            return

        if pendiente_gemini:
            root.after(300, tick)
            return

        if _necesita_captura:
            _necesita_captura = False
            _disparar_gemini()

        root.after(300, tick)

    def _disparar_gemini():
        nonlocal pendiente_gemini
        pendiente_gemini = True

        log_hud("[capture] Ocultando overlay y capturando pantalla...")
        t0 = time.time()
        
        # Ocultar la ventana de tkinter para que no salga en la captura
        root.withdraw()
        root.update()
        time.sleep(0.02)  # 20ms para asegurar el flush del compositor de Windows

        png_bytes = capturar_a_png_bytes(max_dim=1440)

        # Volver a mostrar la ventana
        root.deiconify()
        # Volver a poner topmost porque a veces Windows pierde la jerarquía al ocultar/mostrar
        root.attributes("-topmost", True)
        root.update()

        dt_cap = time.time() - t0

        if png_bytes:
            log_hud(
                f"[capture] PNG listo: {len(png_bytes)//1024}KB "
                f"en {dt_cap:.2f}s → enviando a Gemini..."
            )
            hilo = threading.Thread(
                target=lambda: _analizar_en_gemini(png_bytes),
                daemon=True,
                name="gemini-worker",
            )
            hilo.start()
        else:
            log_hud(f"[capture] ERROR: PNG resultó None ({dt_cap:.2f}s)")
            pendiente_gemini = False

    def _analizar_en_gemini(png_bytes: bytes):
        nonlocal pendiente_gemini
        try:
            from hakunamatata.gemini import analizar_captura

            log_hud(f"[gemini] Iniciando pipeline con {len(png_bytes)//1024}KB...")
            t0 = time.time()
            respuesta = analizar_captura(cliente, png_bytes=png_bytes)
            dt = time.time() - t0

            if respuesta.tiene_respuesta():
                # Convertir múltiples índices correctos a letras (ej: "A, B" o "C")
                letras = []
                indices = getattr(respuesta, "indices_correctos", [])
                if not indices and respuesta.indice_correcto >= 0:
                    indices = [respuesta.indice_correcto]
                
                for idx in sorted(list(set(indices))):
                    if 0 <= idx < len(respuesta.opciones):
                        letras.append(chr(ord('A') + idx))
                
                letra = ", ".join(letras)

                log_hud(
                    f"[gemini] ✅ Respuesta en {dt:.1f}s → "
                    f"opción {respuesta.indice_correcto} ({letra})"
                )

                # Solo actualizamos la interfaz si el mouse sigue en TOP
                if visible:
                    root.after(0, lambda: actualizar_interfaz(letra))
                else:
                    log_hud(
                        "[gemini] Respuesta lista pero el mouse ya salió de TOP → omitiendo dibujo"
                    )
            else:
                log_hud(f"[gemini] ⚠️ Sin respuesta tras {dt:.1f}s")
                if visible:
                    root.after(0, lambda: actualizar_interfaz(""))
        except Exception as e:
            log_hud(f"[gemini] ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
        finally:
            pendiente_gemini = False

    root.after(0, tick)
    root.mainloop()
