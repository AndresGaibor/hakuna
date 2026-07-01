from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field

# Imports que se usan dentro de threads — se cargan aquí (nivel de módulo)
# para evitar el deadlock del import lock de Python cuando el thread
# secundario intenta importar un módulo que el main thread está cargando.
from hakunamatata.hud import log_hud
from hakunamatata.cache import (
    buscar_por_huella_imagen,
    guardar_por_huella_imagen,
    _huella_imagen,
    buscar_por_texto,
    guardar_por_texto,
)

@dataclass
class RespuestaPregunta:
    pregunta: str = ""
    opciones: list[str] = field(default_factory=list)
    indice_correcto: int = -1
    indices_correctos: list[int] = field(default_factory=list)

    @classmethod
    def sin_respuesta(cls) -> RespuestaPregunta:
        return cls()

    def tiene_respuesta(self) -> bool:
        return self.indice_correcto >= 0 or bool(self.indices_correctos)

    def opciones_correctas(self) -> list[str]:
        # Si indices_correctos tiene elementos, los usamos, de lo contrario caemos en indice_correcto
        indices = self.indices_correctos
        if not indices and self.indice_correcto >= 0:
            indices = [self.indice_correcto]
        
        resultado = []
        for idx in indices:
            if 0 <= idx < len(self.opciones):
                resultado.append(self.opciones[idx])
        return resultado


# ── Modelos por etapa ──────────────────────────────────────────────────────────
# Etapa 1 – OCR/extracción: rápido, visión, solo extrae texto
# Orden de prioridad: el primero disponible gana
_MODELOS_OCR = [
    "gemini-3-flash-preview",   # ~290 tok/s, visión nativa excelente
    "gemini-3.5-flash",         # fallback rápido y con visión
    "gemini-3.1-flash-lite",    # fallback barato
]

# Etapa 2 – Razonamiento: inteligente, texto puro (sin imagen)
# Orden de prioridad: el más capaz que esté disponible
_MODELOS_RAZON = [
    "gemini-3.1-pro-preview",   # mejor razonamiento (ARC-AGI, GPQA, HLE)
    "gemini-3-pro-preview",     # fallback razonamiento pro
    "gemini-2.5-pro",           # fallback pro estable
    "gemini-3.5-flash",         # fallback flash muy inteligente
]

# ── Prompts ────────────────────────────────────────────────────────────────────
_SYSTEM_OCR = (
    "Eres un extractor de texto de exámenes. Tu única tarea es leer una "
    "captura de pantalla y extraer fielmente la pregunta y sus opciones. "
    "NO respondas la pregunta. Solo extrae el texto visible. "
    "Ignora menús, barras laterales, logos y cualquier elemento que no sea "
    "la pregunta principal y sus alternativas."
)

_PROMPT_OCR = (
    "Extrae la pregunta de opción múltiple de esta imagen y devuelve ÚNICAMENTE "
    "un JSON sin texto adicional:\n"
    '{"pregunta": "texto completo de la pregunta", '
    '"opciones": ["opcion_a", "opcion_b", "opcion_c", "opcion_d"]}\n\n'
    "IMPORTANTE:\n"
    "- Copia el texto de la imagen exactamente como aparece.\n"
    "- 'opciones' debe ser un array con todas las alternativas en orden.\n"
    "- NO incluyas 'indice_correcto'. Solo extrae texto, no respondas.\n"
    "- Si no hay pregunta visible, devuelve: {\"pregunta\": \"\", \"opciones\": []}"
)

_SYSTEM_RAZON = (
    "Eres un experto resolviendo preguntas de exámenes de opción múltiple. "
    "Razona paso a paso y determina cuál o cuáles alternativas son las correctas. "
    "Soporta tanto preguntas de respuesta única como preguntas de selección múltiple (donde más de una opción es correcta)."
)

_PROMPT_RAZON_TPL = (
    "Pregunta de examen:\n{pregunta}\n\n"
    "Opciones:\n{opciones_fmt}\n\n"
    "Razona brevemente y devuelve ÚNICAMENTE un JSON sin texto adicional:\n"
    '{{"indices_correctos": [0]}}\n\n'
    "Donde 'indices_correctos' es una lista con los índices 0-based de todas las respuestas correctas "
    "(0=primera opción, 1=segunda, etc.). Si solo hay una respuesta correcta, pon solo ese índice en la lista (ej: [2]). "
    "Si no hay suficiente información, devuelve una lista vacía []."
)


def _ruta_config() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    return os.path.join(base, "hakunamatata", "config.json")


def _leer_api_key_persistida() -> str | None:
    ruta = _ruta_config()
    try:
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("api_key")
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _persistir_api_key(api_key: str) -> None:
    ruta = _ruta_config()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"api_key": api_key}, f)
    try:
        os.chmod(ruta, 0o600)
    except OSError:
        pass


def _solicitar_api_key() -> str:
    print("==========================================")
    print("  HAKUNAMATATA - Configuracion inicial")
    print("==========================================")
    print()
    print("Necesitas una API key de Google Gemini.")
    print("Obten una en: https://aistudio.google.com/apikey")
    print()
    key = input("Ingresa tu API key de Gemini: ").strip()
    if not key:
        raise ValueError("API key vacia")
    _persistir_api_key(key)
    print("API key guardada en ~/.config/hakunamatata/config.json")
    return key


def obtener_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    key = _leer_api_key_persistida()
    if key:
        return key
    return _solicitar_api_key()


def crear_cliente(api_key: str | None = None):
    from google import genai

    key = api_key or obtener_api_key()
    return genai.Client(api_key=key)


def _parsear_respuesta_json(texto: str) -> dict | None:
    texto = texto.strip()
    if texto.startswith("```"):
        lineas = texto.split("\n")
        texto = "\n".join(l for l in lineas if not l.startswith("```"))
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
        return None


def _logar_texto_completo(etiqueta: str, texto: str, tamano_bloque: int = 900) -> None:
    if not texto:
        log_hud(f"{etiqueta}: <vacío>")
        return

    total = (len(texto) + tamano_bloque - 1) // tamano_bloque
    for indice in range(0, len(texto), tamano_bloque):
        bloque = texto[indice : indice + tamano_bloque]
        numero = indice // tamano_bloque + 1
        log_hud(f"{etiqueta} [{numero}/{total}]: {bloque}")


_TIMEOUT_API = 50  # segundos máximos por llamada a la API


def _llamar_con_timeout(fn, *args, **kwargs):
    """Ejecuta fn(*args, **kwargs) con timeout duro de _TIMEOUT_API s."""
    resultado = [None]
    excepcion = [None]

    def _worker():
        try:
            resultado[0] = fn(*args, **kwargs)
        except Exception as e:
            excepcion[0] = e

    hilo = threading.Thread(target=_worker, daemon=True)
    hilo.start()
    hilo.join(_TIMEOUT_API)
    if hilo.is_alive():
        raise TimeoutError(
            f"La API no respondió en {_TIMEOUT_API}s — ¿hay conexión a internet?"
        )
    if excepcion[0] is not None:
        raise excepcion[0]
    return resultado[0]


def _etapa_ocr(cliente, png_bytes: bytes) -> tuple[str, list[str]] | None:
    """Etapa 1: extrae pregunta y opciones de la imagen (sin responder)."""
    from google.genai import types

    for modelo in _MODELOS_OCR:
        log_hud(f"[OCR] Llamando a {modelo} ({len(png_bytes)//1024}KB)...")
        try:
            t0 = time.time()
            response = _llamar_con_timeout(
                cliente.models.generate_content,
                model=modelo,
                contents=[
                    _SYSTEM_OCR,
                    _PROMPT_OCR,
                    types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
                ],
            )
            texto = (response.text or "").strip()
            dt = time.time() - t0
            _logar_texto_completo(f"[OCR] {modelo} ({dt:.1f}s)", texto)

            datos = _parsear_respuesta_json(texto)
            if not datos:
                log_hud(f"[OCR] {modelo} no devolvió JSON válido")
                continue

            pregunta = datos.get("pregunta", "").strip()
            opciones = datos.get("opciones", [])
            if pregunta and len(opciones) >= 2:
                log_hud(f"[OCR] OK — {len(opciones)} opciones detectadas")
                return pregunta, opciones
            log_hud(f"[OCR] {modelo} datos insuficientes, probando siguiente...")
        except TimeoutError as e:
            log_hud(f"[OCR] {modelo} TIMEOUT: {e}")
        except Exception as e:
            log_hud(f"[OCR] {modelo} error: {type(e).__name__}: {e}")

    return None


def _etapa_razonamiento(cliente, pregunta: str, opciones: list[str]) -> list[int]:
    """Etapa 2: razona sobre texto puro y devuelve la lista de índices correctos."""
    opciones_fmt = "\n".join(f"{i}. {op}" for i, op in enumerate(opciones))
    prompt = _PROMPT_RAZON_TPL.format(pregunta=pregunta, opciones_fmt=opciones_fmt)

    for modelo in _MODELOS_RAZON:
        log_hud(f"[Razon] Llamando a {modelo} (solo texto)...")
        try:
            t0 = time.time()
            response = _llamar_con_timeout(
                cliente.models.generate_content,
                model=modelo,
                contents=[_SYSTEM_RAZON, prompt],
            )
            texto = (response.text or "").strip()
            dt = time.time() - t0
            _logar_texto_completo(f"[Razon] {modelo} ({dt:.1f}s)", texto)

            datos = _parsear_respuesta_json(texto)
            if datos:
                indices = []
                if "indices_correctos" in datos:
                    val = datos["indices_correctos"]
                    if isinstance(val, list):
                        indices = [int(x) for x in val]
                    elif isinstance(val, (int, float)):
                        indices = [int(val)]
                elif "indice_correcto" in datos:
                    indices = [int(datos["indice_correcto"])]

                # Validar rango
                indices = [idx for idx in indices if 0 <= idx < len(opciones)]
                if indices:
                    log_hud(f"[Razon] Respuesta: opciones {indices} → {[opciones[idx] for idx in indices]}")
                    return sorted(list(set(indices)))
                log_hud(f"[Razon] {modelo} no devolvió índices correctos válidos")
            else:
                log_hud(f"[Razon] {modelo} no devolvió JSON válido")
        except TimeoutError as e:
            log_hud(f"[Razon] {modelo} TIMEOUT: {e}")
        except Exception as e:
            log_hud(f"[Razon] {modelo} error: {type(e).__name__}: {e}")

    return []


def analizar_captura(cliente, png_bytes: bytes | None = None) -> RespuestaPregunta:
    """Pipeline de dos etapas: OCR rápido → razonamiento inteligente."""
    if cliente is None or png_bytes is None:
        log_hud("[analizar] cliente o png_bytes es None — abortando")
        return RespuestaPregunta.sin_respuesta()

    # Caché por huella de imagen
    log_hud(f"[analizar] Calculando huella ({len(png_bytes)//1024}KB)...")
    huella_img = _huella_imagen(png_bytes)
    log_hud(f"[analizar] Buscando en caché (huella={huella_img})...")
    cache = buscar_por_huella_imagen(huella_img)
    if cache:
        log_hud("[analizar] HIT de caché")
        log_hud(f"Pregunta cacheada: {cache['pregunta'][:120]}")
        indices = cache.get("indices_correctos", [])
        if not indices and cache.get("indice_correcto", -1) >= 0:
            indices = [cache["indice_correcto"]]
        return RespuestaPregunta(
            pregunta=cache["pregunta"],
            opciones=cache["opciones"],
            indice_correcto=cache.get("indice_correcto", -1),
            indices_correctos=indices,
        )
    log_hud("[analizar] Sin caché, iniciando pipeline...")

    t_total = time.time()

    # ── Etapa 1: OCR ────────────────────────────────────────────────────
    log_hud("[analizar] Etapa 1/2 — OCR (extraer pregunta de la imagen)")
    try:
        resultado_ocr = _etapa_ocr(cliente, png_bytes)
    except Exception as e:
        log_hud(f"[analizar] ERROR en etapa OCR: {e}")
        for linea in traceback.format_exc().splitlines():
            log_hud(f"  {linea}")
        return RespuestaPregunta.sin_respuesta()

    if resultado_ocr is None:
        log_hud("[analizar] OCR falló en todos los modelos")
        return RespuestaPregunta.sin_respuesta()

    pregunta, opciones = resultado_ocr
    log_hud(f"[analizar] OCR OK — pregunta: {pregunta[:80]!r}")

    # ── NUEVO: Verificar caché por texto antes de llamar al modelo razonador ──
    log_hud("[analizar] Buscando por texto en caché...")
    cache_txt = buscar_por_texto(pregunta, opciones)
    if cache_txt:
        log_hud("[analizar] HIT de caché por texto (se omite etapa de razonamiento) 🎉")
        indices = cache_txt.get("indices_correctos", [])
        if not indices and cache_txt.get("indice_correcto", -1) >= 0:
            indices = [cache_txt["indice_correcto"]]
    else:
        # ── Etapa 2: Razonamiento ─────────────────────────────────────────────
        log_hud("[analizar] Etapa 2/2 — razonamiento (responder la pregunta)")
        try:
            indices = _etapa_razonamiento(cliente, pregunta, opciones)
        except Exception as e:
            log_hud(f"[analizar] ERROR en etapa razonamiento: {e}")
            for linea in traceback.format_exc().splitlines():
                log_hud(f"  {linea}")
            indices = []

    dt = time.time() - t_total
    
    idx_primero = indices[0] if indices else -1
    respuesta = RespuestaPregunta(
        pregunta=pregunta, 
        opciones=opciones, 
        indice_correcto=idx_primero,
        indices_correctos=indices
    )

    if respuesta.tiene_respuesta():
        log_hud(f"[analizar] ✅ Total {dt:.1f}s → opciones {indices}")
        # Guardar en ambos cachés para máxima velocidad en re-triggers futuros
        guardar_por_huella_imagen(huella_img, pregunta, opciones, idx_primero, indices)
        guardar_por_texto(pregunta, opciones, idx_primero, indices)
        log_hud("[analizar] Guardado en caché (imagen y texto)")
    else:
        log_hud(f"[analizar] ⚠️ Sin respuesta tras {dt:.1f}s")

    return respuesta
