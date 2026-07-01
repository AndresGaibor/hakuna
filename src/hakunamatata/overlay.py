from __future__ import annotations

from dataclasses import dataclass

from hakunamatata.answers import PosicionOpcion


@dataclass
class GrupoOverlay:
    posiciones: list[tuple[int, int, int]]
    indice_correcto: int
    color_base: str = "#cccccc"
    color_correcto: str = "#00ff00"


def overlay_opciones(
    opciones: list[PosicionOpcion],
    alto: float,
    *,
    origen_y_arriba: bool,
    filas: int = 4,
) -> list[GrupoOverlay]:
    grupos: list[GrupoOverlay] = []
    grupo_actual: list[PosicionOpcion] = []
    altura_fila = alto / filas

    for op in opciones:
        if not grupo_actual:
            grupo_actual.append(op)
        elif _misma_fila(grupo_actual[0].y, op.y, altura_fila):
            grupo_actual.append(op)
        else:
            grupos.append(_grupo_desde(grupo_actual))
            grupo_actual = [op]

    if grupo_actual:
        grupos.append(_grupo_desde(grupo_actual))

    return grupos


def _misma_fila(y1: float, y2: float, altura_fila: float) -> bool:
    return abs(y1 - y2) < altura_fila


def _grupo_desde(opciones: list[PosicionOpcion]) -> GrupoOverlay:
    correcto = next((i for i, o in enumerate(opciones) if o.es_correcta), -1)
    return GrupoOverlay(
        posiciones=[(o.x, o.y, o.tamano) for o in opciones],
        indice_correcto=correcto,
    )


def calcular_punto(
    ancho: float,
    alto: float,
    *,
    origen_x: float = 0,
    origen_y: float = 0,
    origen_y_arriba: bool = False,
    tamano: int = 34,
    margen: int = 20,
) -> tuple[int, int, int]:
    """Devuelve la posición de un único punto."""

    x = int(origen_x + margen)

    if origen_y_arriba:
        y = int(origen_y + alto - tamano - margen)
    else:
        y = int(origen_y + margen)

    return (x, y, tamano)


def obtener_indice_fila_vertical(
    y: float,
    alto: float,
    *,
    origen_y_arriba: bool,
    filas: int = 4,
) -> int:
    """Devuelve la fila vertical del mouse, numerada desde arriba."""

    if filas <= 0:
        raise ValueError("filas debe ser mayor que cero")
    if alto <= 0:
        raise ValueError("alto debe ser mayor que cero")

    y_desde_arriba = y if origen_y_arriba else alto - y
    altura_fila = alto / filas
    indice = int(y_desde_arriba / altura_fila)
    return max(0, min(filas - 1, indice))


def debe_mostrarse_circulo(
    y: float,
    alto: float,
    *,
    origen_y_arriba: bool,
    filas: int = 4,
) -> bool:
    return obtener_indice_fila_vertical(y, alto, origen_y_arriba=origen_y_arriba, filas=filas) == 0
