from __future__ import annotations

import os
import struct
import subprocess
import shutil
import sys
import tempfile
import time

# ── Caché de ventana Brave (TTL 3s) ─────────────────────────────────────────
_cache_ventana: dict = {"info": None, "ts": 0.0}
_CACHE_VENTANA_TTL = 3.0  # segundos


def tiene_permiso_screen_recording() -> bool:
    if not sys.platform == "darwin":
        return True

    from Quartz import CGPreflightScreenCaptureAccess

    return bool(CGPreflightScreenCaptureAccess())


def solicitar_permiso_screen_recording() -> bool:
    if not sys.platform == "darwin":
        return True

    from Quartz import CGRequestScreenCaptureAccess

    return bool(CGRequestScreenCaptureAccess())


def _dir_debug() -> str:
    # Carpeta debug/ en la raíz del proyecto (dos niveles arriba de este archivo)
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    carpeta = os.path.join(raiz, "debug")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def _ruta_debug_captura(nombre_archivo: str) -> str:
    return os.path.join(_dir_debug(), nombre_archivo)


def _guardar_bytes_debug(nombre_archivo: str, datos: bytes) -> str:
    from hakunamatata.hud import log_hud

    ruta = _ruta_debug_captura(nombre_archivo)
    with open(ruta, "wb") as f:
        f.write(datos)
    log_hud(f"Debug guardado en {ruta}")
    return ruta


def _capturar_display():
    from Quartz import (
        CGDataProviderCopyData,
        CGDisplayCreateImage,
        CGImageGetBytesPerRow,
        CGImageGetDataProvider,
        CGImageGetHeight,
        CGImageGetWidth,
        CGMainDisplayID,
    )

    imagen = CGDisplayCreateImage(CGMainDisplayID())
    if imagen is None:
        raise RuntimeError("CGDisplayCreateImage devolvió None")
    ancho = CGImageGetWidth(imagen)
    alto = CGImageGetHeight(imagen)
    provider = CGImageGetDataProvider(imagen)
    datos = bytes(CGDataProviderCopyData(provider))
    bytes_por_fila = CGImageGetBytesPerRow(imagen)
    return ancho, alto, datos, bytes_por_fila


def _buscar_ventana_brave():
    from hakunamatata.hud import log_hud
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGNullWindowID,
        kCGWindowBounds,
        kCGWindowIsOnscreen,
        kCGWindowLayer,
        kCGWindowListOptionOnScreenOnly,
        kCGWindowName,
        kCGWindowNumber,
        kCGWindowOwnerName,
    )

    # Devolver resultado cacheado si aún es fresco
    ahora = time.monotonic()
    if ahora - _cache_ventana["ts"] < _CACHE_VENTANA_TTL and _cache_ventana["info"] is not None:
        return _cache_ventana["info"]

    ventanas = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
    mejor = None
    mejor_area = 0
    if ventanas:
        for ventana in ventanas:
            owner = str(ventana.get(kCGWindowOwnerName, ""))
            if "Brave" not in owner:
                continue
            if not ventana.get(kCGWindowIsOnscreen, False):
                continue
            if int(ventana.get(kCGWindowLayer, 999)) != 0:
                continue
            window_id = int(ventana.get(kCGWindowNumber, 0))
            if not window_id:
                continue
            # Elegir la ventana Brave más grande (la ventana principal, no popups ni barras)
            bounds = ventana.get(kCGWindowBounds) or {}
            w = int(bounds.get("Width", 0))
            h = int(bounds.get("Height", 0))
            area = w * h
            if area > mejor_area:
                mejor_area = area
                titulo = str(ventana.get(kCGWindowName, ""))
                mejor = (window_id, owner, titulo, w, h)

    if mejor:
        window_id, owner, titulo, w, h = mejor
        log_hud(f"Ventana Brave: windowID={window_id}, {w}x{h}px, title='{titulo}'")
        resultado = (window_id, owner, titulo)
    else:
        log_hud("Brave no encontrado, se usará el display completo")
        resultado = None

    _cache_ventana["info"] = resultado
    _cache_ventana["ts"] = ahora
    return resultado


def _capturar_ventana_macos(window_id: int):
    from Quartz import (
        CGDataProviderCopyData,
        CGImageGetBytesPerRow,
        CGImageGetDataProvider,
        CGImageGetHeight,
        CGImageGetWidth,
        CGWindowListCreateImage,
        CGRectNull,
        kCGWindowImageBoundsIgnoreFraming,
        kCGWindowImageNominalResolution,
        kCGWindowListOptionIncludingWindow,
    )

    imagen = CGWindowListCreateImage(
        CGRectNull,
        kCGWindowListOptionIncludingWindow,
        window_id,
        kCGWindowImageBoundsIgnoreFraming | kCGWindowImageNominalResolution,
    )
    if imagen is None:
        return None

    ancho = CGImageGetWidth(imagen)
    alto = CGImageGetHeight(imagen)
    provider = CGImageGetDataProvider(imagen)
    datos = bytes(CGDataProviderCopyData(provider))
    bytes_por_fila = CGImageGetBytesPerRow(imagen)
    return ancho, alto, datos, bytes_por_fila


def capturar_macos_bmp_sin_overlay(ruta_bmp: str, window_number: int) -> None:
    ventana = _buscar_ventana_brave()
    if ventana:
        window_id, _owner, _titulo = ventana
        capturado = _capturar_ventana_macos(window_id)
    else:
        capturado = None

    if capturado is None:
        ancho, alto, datos, bytes_por_fila = _capturar_display()
    else:
        ancho, alto, datos, bytes_por_fila = capturado

    buffer = bytearray()
    for y in range(alto - 1, -1, -1):
        inicio = y * bytes_por_fila
        buffer.extend(datos[inicio : inicio + ancho * 4])

    _escribir_bmp(ruta_bmp, ancho, alto, buffer)


def capturar_windows_bmp(ruta_bmp: str) -> None:
    import ctypes
    from ctypes import wintypes

    windll = getattr(ctypes, "windll")
    user32 = windll.user32
    gdi32 = windll.gdi32

    ancho = user32.GetSystemMetrics(0)
    alto = user32.GetSystemMetrics(1)
    hdc_screen = user32.GetDC(0)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, ancho, alto)
    gdi32.SelectObject(hdc_mem, hbmp)
    gdi32.BitBlt(hdc_mem, 0, 0, ancho, alto, hdc_screen, 0, 0, 0x00CC0020)

    class BITMAPFILEHEADER(ctypes.Structure):
        _fields_ = [
            ("bfType", wintypes.WORD),
            ("bfSize", wintypes.DWORD),
            ("bfReserved1", wintypes.WORD),
            ("bfReserved2", wintypes.WORD),
            ("bfOffBits", wintypes.DWORD),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = ancho
    bi.biHeight = alto
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0

    buffer_size = ancho * alto * 4
    buffer = (ctypes.c_ubyte * buffer_size)()
    gdi32.GetDIBits(hdc_screen, hbmp, 0, alto, buffer, ctypes.byref(bi), 0)

    file_header = BITMAPFILEHEADER()
    file_header.bfType = 0x4D42
    file_header.bfOffBits = ctypes.sizeof(BITMAPFILEHEADER) + ctypes.sizeof(BITMAPINFOHEADER)
    file_header.bfSize = file_header.bfOffBits + buffer_size

    with open(ruta_bmp, "wb") as f:
        f.write(bytes(file_header))
        f.write(bytes(bi))
        f.write(bytes(buffer))

    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(0, hdc_screen)


def leer_bmp(ruta: str):
    with open(ruta, "rb") as f:
        data = f.read()

    if data[:2] != b"BM":
        raise ValueError("BMP inválido")

    offset = struct.unpack_from("<I", data, 10)[0]
    ancho = struct.unpack_from("<I", data, 18)[0]
    alto = struct.unpack_from("<I", data, 22)[0]
    bits = struct.unpack_from("<H", data, 28)[0]
    bytes_por_pixel = bits // 8
    fila_bytes = ((ancho * bytes_por_pixel + 3) // 4) * 4

    pixeles = []
    for y in range(alto):
        fila = []
        real_y = alto - 1 - y
        inicio = offset + real_y * fila_bytes
        for x in range(ancho):
            i = inicio + x * bytes_por_pixel
            b = data[i]
            g = data[i + 1]
            r = data[i + 2]
            fila.append(int((r + g + b) / 3))
        pixeles.append(fila)

    return pixeles, ancho, alto


def ocultar_region(imagen: list[list[int]], x: int, y: int, tamano: int, *, origen_y_arriba: bool) -> None:
    alto = len(imagen)
    ancho = len(imagen[0]) if alto else 0
    if alto == 0 or ancho == 0:
        return

    inicio_x = max(0, x)
    fin_x = min(ancho, x + tamano)
    if origen_y_arriba:
        inicio_y = max(0, y)
        fin_y = min(alto, y + tamano)
    else:
        inicio_y = max(0, alto - (y + tamano))
        fin_y = min(alto, alto - y)

    for fila in range(inicio_y, fin_y):
        for columna in range(inicio_x, fin_x):
            imagen[fila][columna] = 0


def capturar_pantalla_a_pixeles(*, window_number: int | None = None):
    with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
        ruta_tmp = tmp.name

    try:
        if sys.platform == "darwin":
            if window_number is None:
                raise ValueError("window_number requerido en macOS")
            capturar_macos_bmp_sin_overlay(ruta_tmp, window_number)
            shutil.copyfile(ruta_tmp, _ruta_debug_captura("haku_capture_raw.bmp"))
        elif sys.platform.startswith("win"):
            capturar_windows_bmp(ruta_tmp)
            shutil.copyfile(ruta_tmp, _ruta_debug_captura("haku_capture_raw.bmp"))
        else:
            raise SystemExit("Plataforma no soportada")

        pixeles, _ancho, _alto = leer_bmp(ruta_tmp)
        return pixeles
    finally:
        if os.path.exists(ruta_tmp):
            os.remove(ruta_tmp)


def capturar_a_png_bytes(window_number: int | None = None, max_dim: int = 1440) -> bytes | None:
    try:
        if sys.platform == "darwin":
            if window_number is None:
                return None
            return _capturar_macos_a_png(window_number, max_dim)
        elif sys.platform.startswith("win"):
            return _capturar_windows_a_png(max_dim)
        return None
    except Exception:
        return None


def _capturar_macos_a_png(window_number: int, max_dim: int = 1440) -> bytes:
    """Captura el display completo para mandarlo a Gemini.

    Nota: CGWindowListCreateImage NO puede capturar el contenido de navegadores
    basados en Chromium (Brave, Chrome) porque usan aceleración GPU.
    Solo devuelve el chrome del navegador (barra de pestañas, ~41px).
    CGDisplayCreateImage sí captura el frame compuesto final con todo el contenido.
    """
    import io
    from PIL import Image
    from hakunamatata.hud import log_hud

    ancho, alto, datos, bytes_por_fila = _capturar_display()
    log_hud(f"Display capturado: {ancho}x{alto} px")

    # Quartz entrega top→bottom (NO invertir filas, eso es solo para BMP).
    # Formato BGRA en little-endian → usar decoder "BGRA" en PIL.
    bytes_por_pixel = 4
    stride_dst = ancho * bytes_por_pixel
    if bytes_por_fila == stride_dst:
        raw = bytes(datos[: ancho * alto * bytes_por_pixel])
    else:
        raw_buf = bytearray(ancho * alto * bytes_por_pixel)
        for row in range(alto):
            raw_buf[row * stride_dst : (row + 1) * stride_dst] = \
                datos[row * bytes_por_fila : row * bytes_por_fila + stride_dst]
        raw = bytes(raw_buf)

    img = Image.frombytes("RGBA", (ancho, alto), raw, "raw", "BGRA")

    # Recortar los 45 píxeles superiores para excluir la barra de menús de macOS,
    # el notch, la hora del sistema y las pestañas del navegador.
    # Esto estabiliza la huella de imagen para que el caché no falle por cambios de la hora.
    img = img.crop((0, 45, ancho, alto))
    ancho_crop, alto_crop = img.size

    if max_dim and max(ancho_crop, alto_crop) > max_dim:
        escala = max_dim / max(ancho_crop, alto_crop)
        img = img.resize(
            (int(ancho_crop * escala), int(alto_crop * escala)), Image.LANCZOS
        )

    png_buf = io.BytesIO()
    img.save(png_buf, format="PNG")
    png_bytes = png_buf.getvalue()
    log_hud(f"PNG generado: {len(png_bytes)} bytes ({len(png_bytes)//1024}KB)")
    _guardar_bytes_debug("haku_capture_sent.png", png_bytes)
    return png_bytes


def _capturar_windows_a_png(max_dim: int = 1440) -> bytes:
    import io
    from PIL import Image
    import ctypes
    from ctypes import wintypes

    windll = getattr(ctypes, "windll")
    user32 = windll.user32
    gdi32 = windll.gdi32

    ancho = user32.GetSystemMetrics(0)
    alto = user32.GetSystemMetrics(1)
    hdc_screen = user32.GetDC(0)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, ancho, alto)
    gdi32.SelectObject(hdc_mem, hbmp)
    gdi32.BitBlt(hdc_mem, 0, 0, ancho, alto, hdc_screen, 0, 0, 0x00CC0020)

    buffer_size = ancho * alto * 4
    buffer = (ctypes.c_ubyte * buffer_size)()
    gdi32.GetBitmapBits(hbmp, buffer_size, buffer)

    # Windows GDI entrega en formato BGRA (BGR + Alpha).
    # Usamos el decoder "BGRA" para mapear los canales correctamente en Pillow.
    img = Image.frombytes("RGBA", (ancho, alto), bytes(buffer), "raw", "BGRA")

    # Recortar 40 píxeles arriba (barra de título) y 40 píxeles abajo (barra de tareas)
    # para estabilizar la huella de la imagen en caché.
    img = img.crop((0, 40, ancho, alto - 40))
    ancho_crop, alto_crop = img.size

    if max_dim and max(ancho_crop, alto_crop) > max_dim:
        escala = max_dim / max(ancho_crop, alto_crop)
        nuevo_ancho = int(ancho_crop * escala)
        nuevo_alto = int(alto_crop * escala)
        img = img.resize((nuevo_ancho, nuevo_alto), Image.LANCZOS)

    png_buf = io.BytesIO()
    img.save(png_buf, format="PNG")
    _guardar_bytes_debug("haku_capture_sent.png", png_buf.getvalue())

    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(0, hdc_screen)
    return png_buf.getvalue()


def _escribir_bmp(ruta_bmp: str, ancho: int, alto: int, buffer: bytearray) -> None:
    header_size = 14 + 40
    file_size = header_size + len(buffer)
    with open(ruta_bmp, "wb") as f:
        f.write(b"BM")
        f.write(struct.pack("<IHHI", file_size, 0, 0, header_size))
        f.write(struct.pack("<IIIHHIIIIII", 40, ancho, alto, 1, 32, 0, len(buffer), 0, 0, 0, 0))
        f.write(buffer)
