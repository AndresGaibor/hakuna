from __future__ import annotations

import colorsys
import hashlib
from dataclasses import dataclass


@dataclass
class EstadoDeteccion:
    anterior: str | None = None
    paso: int = 0
    color_hex: str = "#ff0000"


def debe_cambiar_color(similitud: float, umbral: float) -> bool:
    return similitud < umbral


def crear_huella_visual(imagen: list[list[int]]) -> str:
    hasher = hashlib.blake2b(digest_size=16)
    for fila in imagen:
        hasher.update(bytes(fila))
    return hasher.hexdigest()


def color_desde_paso(paso: int) -> str:
    hue = (paso * 0.61803398875) % 1.0
    rojo_f, verde_f, azul_f = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
    return f"#{int(rojo_f * 255):02x}{int(verde_f * 255):02x}{int(azul_f * 255):02x}"


def actualizar_estado(estado: EstadoDeteccion, captura: list[list[int]]) -> bool:
    huella_actual = crear_huella_visual(captura)

    if estado.anterior is None:
        estado.anterior = huella_actual
        estado.color_hex = color_desde_paso(estado.paso)
        return True

    if huella_actual != estado.anterior:
        estado.paso += 1
        estado.anterior = huella_actual
        estado.color_hex = color_desde_paso(estado.paso)
        return True

    return False
