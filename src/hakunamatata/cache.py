from __future__ import annotations

import hashlib
import json
import os
import sys


def _ruta_cache() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    return os.path.join(base, "hakunamatata", "cache.json")


def _huella_imagen(png_bytes: bytes) -> str:
    return hashlib.sha256(png_bytes).hexdigest()[:16]


def _huella_texto(pregunta: str, opciones: list[str]) -> str:
    # Identificar la pregunta de forma unívoca basándonos en el texto de la pregunta y las opciones
    payload = pregunta.strip() + "|" + "|".join(op.strip() for op in opciones)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _cargar_cache() -> dict[str, dict]:
    ruta = _ruta_cache()
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _guardar_cache(cache: dict[str, dict]) -> None:
    ruta = _ruta_cache()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def buscar_por_huella_imagen(huella: str) -> dict | None:
    return _cargar_cache().get(huella)


def guardar_por_huella_imagen(
    huella: str,
    pregunta: str,
    opciones: list[str],
    indice_correcto: int,
    indices_correctos: list[int] | None = None,
) -> None:
    cache = _cargar_cache()
    cache[huella] = {
        "pregunta": pregunta,
        "opciones": opciones,
        "indice_correcto": indice_correcto,
        "indices_correctos": indices_correctos or ([indice_correcto] if indice_correcto >= 0 else []),
    }
    _guardar_cache(cache)


def buscar_por_texto(pregunta: str, opciones: list[str]) -> dict | None:
    huella = _huella_texto(pregunta, opciones)
    return _cargar_cache().get(huella)


def guardar_por_texto(
    pregunta: str,
    opciones: list[str],
    indice_correcto: int,
    indices_correctos: list[int] | None = None,
) -> None:
    huella = _huella_texto(pregunta, opciones)
    cache = _cargar_cache()
    cache[huella] = {
        "pregunta": pregunta,
        "opciones": opciones,
        "indice_correcto": indice_correcto,
        "indices_correctos": indices_correctos or ([indice_correcto] if indice_correcto >= 0 else []),
    }
    _guardar_cache(cache)
