from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PosicionOpcion:
    x: int
    y: int
    tamano: int = 34
    es_correcta: bool = False


def calcular_posiciones_opciones(
    ancho: float,
    alto: float,
    num_opciones: int,
    *,
    margen_x: int = 40,
    inicio_y_ratio: float = 0.35,
    espaciado_ratio: float = 0.08,
) -> list[PosicionOpcion]:
    posiciones: list[PosicionOpcion] = []
    inicio_y = int(alto * inicio_y_ratio)
    espaciado = int(alto * espaciado_ratio)

    for i in range(num_opciones):
        posiciones.append(PosicionOpcion(x=margen_x, y=inicio_y + i * espaciado))
    return posiciones


def marcar_respuesta_correcta(
    posiciones: list[PosicionOpcion],
    indice_correcto: int,
) -> list[PosicionOpcion]:
    for i, p in enumerate(posiciones):
        if i == indice_correcto:
            p.es_correcta = True
    return posiciones
