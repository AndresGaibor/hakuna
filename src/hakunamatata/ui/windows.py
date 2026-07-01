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
    ultima_respuesta: str = ""   # Guarda la última letra calculada

    color_transparente = "magenta"
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-disabled", True)
    root.configure(bg=color_transparente)
    root.geometry(f"{ancho}x{alto}+0+0")
    root.wm_attributes("-transparentcolor", color_transparente)
    root.attributes("-alpha", 0.45)  # Semi-transparente para ser disimulado

    canvas = tk.Canvas(root, bg=color_transparente, highlightthickness=0, borderwidth=0)
    canvas.pack(fill="both", expand=True)

    text_id = None
    shadow_id = None

    def actualizar_interfaz(texto):
        """Actualiza el texto en pantalla. Se ejecuta de forma segura en el hilo principal."""
        nonlocal text_id, shadow_id
        if shadow_id is not None:
            canvas.delete(shadow_id)
            shadow_id = None
        if text_id is not None:
            canvas.delete(text_id)
            text_id = None
        if texto:
            x = 40
            y = alto - 75
            # Sombra negra para legibilidad sobre cualquier fondo
            shadow_id = canvas.create_text(
                x + 1, y + 1,
                text=texto,
                font=("Arial", 10, "bold"),
                fill="#000000",
                anchor="sw",
            )
            # Texto principal blanco — discreto pero legible
            text_id = canvas.create_text(
                x, y,
                text=texto,
                font=("Arial", 10, "bold"),
                fill="#C0C0C0",
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
                # Entrando a TOP:
                # Si no hay escaneo pendiente en background, limpiamos la respuesta anterior
                # y mostramos el indicador de escaneo '..' para no confundir al usuario.
                if not pendiente_gemini:
                    ultima_respuesta = ""
                    actualizar_interfaz("..")
                    _necesita_captura = True
                else:
                    # Si ya hay una petición corriendo en segundo plano, mostramos su estado actual
                    if ultima_respuesta:
                        actualizar_interfaz(ultima_respuesta)
                    else:
                        actualizar_interfaz("..")
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
        nonlocal pendiente_gemini, ultima_respuesta
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
                ultima_respuesta = letra  # Guardar siempre, independientemente del mouse

                log_hud(
                    f"[gemini] ✅ Respuesta en {dt:.1f}s → "
                    f"opción {respuesta.indice_correcto} ({letra})"
                )

                # Mostrar si el mouse está en TOP; si no, se mostrará la próxima vez que entre
                if visible:
                    root.after(0, lambda: actualizar_interfaz(letra))
                else:
                    log_hud(
                        f"[gemini] Mouse fuera de TOP — respuesta '{letra}' guardada, "
                        f"se mostrará al volver a TOP"
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
