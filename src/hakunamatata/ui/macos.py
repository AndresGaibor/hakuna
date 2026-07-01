from __future__ import annotations

import signal
import threading
import time

import objc

from hakunamatata.answers import calcular_posiciones_opciones, marcar_respuesta_correcta
from hakunamatata.capture import (
    capturar_a_png_bytes,
    capturar_pantalla_a_pixeles,
    ocultar_region,
    solicitar_permiso_screen_recording,
    tiene_permiso_screen_recording,
)
from hakunamatata.detection import EstadoDeteccion, actualizar_estado
from hakunamatata.hud import log_hud
from hakunamatata.overlay import GrupoOverlay, overlay_opciones
from hakunamatata.mouse import obtener_posicion_mouse


def ejecutar(cliente=None) -> None:
    from Cocoa import (
        NSObject,
        NSApplication,
        NSBackingStoreBuffered,
        NSBezierPath,
        NSColor,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorStationary,
        NSMakeRect,
        NSPanel,
        NSScreen,
        NSTimer,
        NSView,
        NSWindowSharingNone,
        NSString,
        NSFont,
        NSMutableParagraphStyle,
        NSFontAttributeName,
        NSForegroundColorAttributeName,
        NSParagraphStyleAttributeName,
    )
    from Quartz import CGWindowLevelForKey, kCGScreenSaverWindowLevelKey

    from hakunamatata.hud import iniciar_hud
    from hakunamatata.gemini import _MODELOS_OCR, _MODELOS_RAZON

    class DotView(NSView):
        def drawRect_(self, rect):
            NSColor.clearColor().set()
            
            texto = getattr(self, "respuesta_texto", "")
            log_hud(f"[DotView] drawRect_ ejecutado (texto={repr(texto)})")
            
            # Dibujar la respuesta textual en la esquina inferior izquierda
            if texto:
                # Fuente diminuta (10) y color negro extremadamente semitranslúcido (alpha = 0.16)
                font = NSFont.boldSystemFontOfSize_(10)
                color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.0, 0.0, 0.16)
                
                attrs = {
                    NSFontAttributeName: font,
                    NSForegroundColorAttributeName: color,
                }
                
                # Dibujar el texto directamente (sin recuadro ni fondo oscuro)
                text_rect = NSMakeRect(35, 35, 200, 30)
                str_obj = NSString.stringWithString_(texto)
                str_obj.drawInRect_withAttributes_(text_rect, attrs)


    class ControladorCaptura(NSObject):
        def initWithView_window_client_(self, view, window, cliente):
            self = objc.super(ControladorCaptura, self).init()
            self.view = view
            self.window = window
            self.estado = EstadoDeteccion()
            self.cliente = cliente
            self.visible = None
            self.grupos_actuales: list[GrupoOverlay] = []
            self.respuesta_texto = ""
            self.pendiente_gemini = False
            self.captura_pendiente = None
            self.png_pendiente = None
            self._lock = threading.Lock()
            self._tick_count = 0
            self._ultimo_envio_ts = 0.0
            self._necesita_captura = False
            log_hud("Controlador inicializado (timer=0.3s)")
            return self

        def actualizarInterface_(self, info):
            """Actualiza la vista de dibujo. Debe ejecutarse en el hilo principal (main thread)."""
            grupos, texto = info
            self.view.grupos_actuales = grupos
            self.view.respuesta_texto = texto
            self.view.setNeedsDisplay_(True)


        def tick_(self, _timer):
            self._tick_count += 1
            from hakunamatata.overlay import debe_mostrarse_circulo

            _, mouse_y = obtener_posicion_mouse()
            frame_origin_y = self.window.frame().origin.y
            frame_height = self.window.frame().size.height
            y_rel = mouse_y - frame_origin_y

            visible = debe_mostrarse_circulo(y_rel, frame_height, origen_y_arriba=False)

            # ── Detectar transiciones de visibilidad ───────────────────────────────
            if visible != self.visible:
                self.visible = visible
                log_hud(f"Mouse {'en TOP ✓' if visible else 'fuera de TOP ✗'} (y={int(mouse_y)})")
                if visible:
                    # Entrando a TOP: limpiar el overlay anterior inmediatamente
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        "actualizarInterface:", ([], ""), False
                    )
                    with self._lock:
                        self.grupos_actuales = []
                        self.respuesta_texto = ""
                    
                    self._necesita_captura = True
                    log_hud("Flag de captura activado")
                else:
                    # Saliendo de TOP: limpiar la pantalla inmediatamente
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        "actualizarInterface:", ([], ""), False
                    )
                    with self._lock:
                        self.grupos_actuales = []
                        self.respuesta_texto = ""
                    if not self.pendiente_gemini:
                        self._necesita_captura = False
                    else:
                        log_hud("Mouse salió pero Gemini sigue corriendo → flag conservado")

            # ── Fuera del TOP y sin Gemini pendiente: no hacer nada extra ──────
            if not visible:
                return

            if self.pendiente_gemini:
                return

            # ── Disparar captura si se necesita ─────────────────────────────
            if self._necesita_captura:
                log_hud("Iniciando captura...")
                self._necesita_captura = False
                self._disparar_gemini()
                return

        def _disparar_gemini(self):
            """Captura el PNG actual y lanza el hilo de análisis en background."""
            self.pendiente_gemini = True
            self._ultimo_envio_ts = time.time()
            log_hud("[capture] Tomando captura de pantalla...")
            t0 = time.time()
            
            # Ocultar el panel de overlay de la pantalla para no capturar los propios dibujos del overlay
            self.window.setAlphaValue_(0.0)
            time.sleep(0.02)  # 20ms (imperceptible) para asegurar el flush del window server
            
            self.png_pendiente = capturar_a_png_bytes(
                window_number=self.window.windowNumber(), max_dim=1440
            )
            
            # Restaurar visibilidad del overlay
            self.window.setAlphaValue_(1.0)
            
            dt_cap = time.time() - t0
            if self.png_pendiente:
                log_hud(
                    f"[capture] PNG listo: {len(self.png_pendiente)//1024}KB "
                    f"en {dt_cap:.2f}s → enviando a Gemini..."
                )
            else:
                log_hud(f"[capture] ERROR: PNG resultó None ({dt_cap:.2f}s)")
            self.captura_pendiente = None
            hilo = threading.Thread(
                target=self._analizar_en_gemini, daemon=True, name="gemini-worker"
            )
            hilo.start()
            log_hud(f"[gemini] Hilo de análisis lanzado (thread={hilo.name})")

        def _analizar_en_gemini(self):
            import traceback
            try:
                from hakunamatata.gemini import analizar_captura

                png = self.png_pendiente
                if png is None:
                    log_hud("[gemini] ERROR: PNG es None, abortando")
                    return
                if len(png) == 0:
                    log_hud("[gemini] ERROR: PNG vacío (0 bytes), abortando")
                    return

                log_hud(f"[gemini] Iniciando pipeline con {len(png)//1024}KB...")
                t0 = time.time()
                respuesta = analizar_captura(self.cliente, png_bytes=png)
                dt = time.time() - t0

                if respuesta.tiene_respuesta():
                    log_hud(
                        f"[gemini] ✅ Respuesta en {dt:.1f}s → "
                        f"opción {respuesta.indice_correcto}: "
                        f"{respuesta.opciones[respuesta.indice_correcto]!r}"
                    )
                    log_hud(f"[gemini] Pregunta: {respuesta.pregunta[:120]}")

                    # Convertir múltiples índices correctos a letras (ej: "A, B" o "C")
                    letras = []
                    indices = getattr(respuesta, "indices_correctos", [])
                    if not indices and respuesta.indice_correcto >= 0:
                        indices = [respuesta.indice_correcto]
                    
                    for idx in sorted(list(set(indices))):
                        if 0 <= idx < len(respuesta.opciones):
                            letras.append(chr(ord('A') + idx))
                    
                    letra = ", ".join(letras)

                    captura = self.captura_pendiente
                    ancho = len(captura[0]) if captura else 1920
                    alto = len(captura) if captura else 1080
                    log_hud(f"[overlay] Calculando posiciones ({ancho}x{alto})...")
                    posiciones = calcular_posiciones_opciones(
                        ancho, alto, len(respuesta.opciones)
                    )
                    posiciones_marcadas = marcar_respuesta_correcta(
                        posiciones, respuesta.indice_correcto
                    )
                    frame_height = self.window.frame().size.height
                    grupos = overlay_opciones(
                        posiciones_marcadas,
                        alto=frame_height,
                        origen_y_arriba=False,
                    )
                    log_hud(f"[overlay] Mostrando {len(grupos)} grupos")
                    with self._lock:
                        self.grupos_actuales = grupos
                        self.respuesta_texto = letra
                    
                    # Solo actualizamos e indicamos redibujar si el mouse sigue en TOP
                    if self.visible:
                        self.performSelectorOnMainThread_withObject_waitUntilDone_(
                            "actualizarInterface:", (grupos, letra), False
                        )
                    else:
                        log_hud("[gemini] Respuesta lista pero el mouse ya salió de TOP → omitiendo dibujo")
                else:
                    log_hud(f"[gemini] ⚠️ Sin respuesta tras {dt:.1f}s")
                    with self._lock:
                        self.respuesta_texto = ""
                    if self.visible:
                        self.performSelectorOnMainThread_withObject_waitUntilDone_(
                            "actualizarInterface:", ([], ""), False
                        )
            except Exception as e:
                log_hud(f"[gemini] EXCEPCIÓN: {type(e).__name__}: {e}")
                for linea in traceback.format_exc().splitlines():
                    log_hud(f"  {linea}")
            finally:
                log_hud("[gemini] Análisis finalizado. Saca y vuelve a subir el mouse para escanear otra vez.")
                self.pendiente_gemini = False
                self.captura_pendiente = None
                self.png_pendiente = None

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)

    log_hud("Iniciando overlay macOS...")
    log_hud(f"Cliente Gemini {'configurado' if cliente else 'NO configurado (⚠️ sin API key)'}")
    log_hud(f"Modelos OCR: {', '.join(_MODELOS_OCR)}")
    log_hud(f"Modelos razonamiento: {', '.join(_MODELOS_RAZON)}")
    if not tiene_permiso_screen_recording():
        log_hud("Falta permiso de Screen Recording; pidiéndolo ahora...")
        if solicitar_permiso_screen_recording():
            log_hud("Permiso solicitado. Cierra y vuelve a abrir el script si macOS lo requiere.")
        else:
            log_hud("Permiso de Screen Recording no concedido.")
        log_hud("No continuaré para evitar capturar el fondo de pantalla.")
        return
    screen = NSScreen.mainScreen().visibleFrame()
    log_hud(f"Pantalla: {int(screen.size.width)}x{int(screen.size.height)}")

    rect = NSMakeRect(screen.origin.x, screen.origin.y, screen.size.width, screen.size.height)

    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        rect, 1 << 5, NSBackingStoreBuffered, False
    )
    panel.setOpaque_(False)
    panel.setBackgroundColor_(NSColor.clearColor())
    panel.setHasShadow_(False)
    panel.setSharingType_(NSWindowSharingNone)
    panel.setLevel_(CGWindowLevelForKey(kCGScreenSaverWindowLevelKey))
    panel.setIgnoresMouseEvents_(True)
    panel.setFloatingPanel_(True)
    panel.setHidesOnDeactivate_(False)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces
        | NSWindowCollectionBehaviorFullScreenAuxiliary
        | NSWindowCollectionBehaviorStationary
    )

    # El frame de la vista interna debe comenzar en (0, 0) relativo al contenido del panel,
    # no en las coordenadas absolutas de la pantalla (rect.origin.x, rect.origin.y).
    view_rect = NSMakeRect(0, 0, rect.size.width, rect.size.height)
    view = DotView.alloc().initWithFrame_(view_rect)
    view.grupos_actuales = []
    view.respuesta_texto = ""
    view.setHidden_(False)  # Mantener siempre visible (transparente e interactivo)

    panel.setContentView_(view)
    panel.orderFrontRegardless()
    log_hud("Overlay listo. Sube el mouse al borde superior.")

    app.activateIgnoringOtherApps_(True)

    controlador = ControladorCaptura.alloc().initWithView_window_client_(
        view, panel, cliente
    )
    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        0.3, controlador, "tick:", None, True
    )

    # ── Run loop manual ─────────────────────────────────────────────────────
    # app.run() bloquea en ObjC y nunca deja que Python procese señales.
    # Corremos el NSRunLoop en tramos cortos para que Ctrl+C funcione.
    from Foundation import NSRunLoop, NSDate

    _corriendo = [True]

    def _salir_signal(signum, frame):
        log_hud("\n[HAKU] Ctrl+C recibido, saliendo...")
        _corriendo[0] = False

    signal.signal(signal.SIGINT, _salir_signal)
    signal.signal(signal.SIGTERM, _salir_signal)

    run_loop = NSRunLoop.currentRunLoop()
    while _corriendo[0]:
        run_loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
