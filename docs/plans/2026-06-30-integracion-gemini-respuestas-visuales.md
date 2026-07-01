# Integración Gemini + Respuestas Visuales

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrar Gemini API para que el overlay capture la pantalla, la envíe a Gemini, y muestre la respuesta como círculos en la posición correcta sobre la pantalla.

**Architecture:** El flujo existente de captura-detección se extiende con un cliente Gemini (`gemini.py`) que envía la captura como imagen base64 y recibe la respuesta. Un módulo de análisis (`answers.py`) parsea la respuesta para determinar qué opción es correcta. El overlay se modifica para mostrar múltiples círculos (uno por opción) con el círculo de la respuesta correcta resaltado. Todo se integra en los UI loops de macOS y Windows.

**Tech Stack:** Python 3.12, `uv`, `google-genai>=1.0.0`, PyObjC (macOS), Tkinter (Windows)

---

### Task 1: Agregar dependencia google-genai

**Files:**
- Modify: `pyproject.toml`

**Step 1: Editar pyproject.toml**

Agregar `"google-genai>=1.0.0"` a la lista de dependencias.

**Step 2: Verificar instalación**

Run: `uv sync`
Expected: google-genai instalado sin errores.

**Step 3: Commit**

No commit aún.

---

### Task 2: Crear módulo gemini.py - Cliente API Gemini

**Files:**
- Create: `src/hakunamatata/gemini.py`
- Test: `tests/test_gemini.py`

**Step 1: Escribir el test que falla**

```python
import unittest
from unittest.mock import patch, MagicMock

from hakunamatata.gemini import crear_cliente, analizar_captura, RespuestaPregunta


class TestGemini(unittest.TestCase):
    def test_crear_cliente_con_api_key(self):
        cliente = crear_cliente("test-key")
        self.assertIsNotNone(cliente)

    def test_analizar_captura_parsea_respuesta_correcta(self):
        captura = [[100] * 10 for _ in range(10)]
        resultado = analizar_captura(None, captura)
        self.assertIsInstance(resultado, RespuestaPregunta)
        self.assertIn(resultado.indice_correcto, range(4))

    def test_respuesta_pregunta_almacena_opciones(self):
        r = RespuestaPregunta(
            pregunta="¿Cuánto es 2+2?",
            opciones=["1", "2", "3", "4"],
            indice_correcto=3,
        )
        self.assertEqual(r.opciones_correctas(), ["4"])

    def test_respuesta_sin_respuesta_clara(self):
        r = RespuestaPregunta.sin_respuesta()
        self.assertFalse(r.tiene_respuesta())
```

**Step 2: Ejecutar test para verificar que falla**

Run: `uv run python -m unittest tests.test_gemini -v`
Expected: FAIL - ModuleNotFoundError para hakunamatata.gemini

**Step 3: Implementación mínima**

```python
from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass, field


@dataclass
class RespuestaPregunta:
    pregunta: str = ""
    opciones: list[str] = field(default_factory=list)
    indice_correcto: int = -1

    @classmethod
    def sin_respuesta(cls) -> RespuestaPregunta:
        return cls()

    def tiene_respuesta(self) -> bool:
        return self.indice_correcto >= 0

    def opciones_correctas(self) -> list[str]:
        if self.indice_correcto < 0 or self.indice_correcto >= len(self.opciones):
            return []
        return [self.opciones[self.indice_correcto]]


def crear_cliente(api_key: str | None = None):
    from google import genai

    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY no configurada")
    return genai.Client(api_key=key)


def _captura_a_bytes(captura: list[list[int]]) -> bytes:
    import struct

    alto = len(captura)
    ancho = len(captura[0]) if alto else 0
    if alto == 0 or ancho == 0:
        return b""

    buffer = bytearray()
    for y in range(alto - 1, -1, -1):
        for x in range(ancho):
            g = captura[y][x]
            buffer.extend(struct.pack("BBBB", g, g, g, 255))

    bmp_bytes = bytearray()
    header_size = 14 + 40
    file_size = header_size + len(buffer)
    bmp_bytes.extend(b"BM")
    bmp_bytes.extend(struct.pack("<IHHI", file_size, 0, 0, header_size))
    bmp_bytes.extend(struct.pack("<IIIHHIIIIII", 40, ancho, alto, 1, 32, 0, len(buffer), 0, 0, 0, 0))
    bmp_bytes.extend(buffer)
    return bytes(bmp_bytes)


def _bmp_a_png_bytes(bmp_bytes: bytes) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(bmp_bytes))
    png_buf = io.BytesIO()
    img.save(png_buf, format="PNG")
    return png_buf.getvalue()


PROMPT_DEFAULT = (
    "Eres un asistente de exámenes. Analiza la imagen de la pantalla, "
    "identifica la pregunta y las opciones de respuesta. "
    "Devuelve ÚNICAMENTE un JSON con esta estructura exacta:\n"
    '{"pregunta": "texto de la pregunta", '
    '"opciones": ["opcion_a", "opcion_b", "opcion_c", "opcion_d"], '
    '"indice_correcto": 0}\n'
    "Donde indice_correcto es el índice (0-based) de la opción correcta. "
    "Si no puedes determinar la respuesta, usa indice_correcto: -1."
)


def analizar_captura(
    cliente,
    captura: list[list[int]],
    prompt: str = PROMPT_DEFAULT,
) -> RespuestaPregunta:
    from google.genai import types

    if cliente is None:
        return RespuestaPregunta.sin_respuesta()

    try:
        bmp_bytes = _captura_a_bytes(captura)
        png_bytes = _bmp_a_png_bytes(bmp_bytes)

        contents = [
            prompt,
            types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
        ]

        response = cliente.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        )

        texto = response.text.strip()
        import json

        if texto.startswith("```"):
            lineas = texto.split("\n")
            texto = "\n".join(l for l in lineas if not l.startswith("```"))

        datos = json.loads(texto)
        return RespuestaPregunta(
            pregunta=datos.get("pregunta", ""),
            opciones=datos.get("opciones", []),
            indice_correcto=datos.get("indice_correcto", -1),
        )
    except Exception:
        return RespuestaPregunta.sin_respuesta()
```

**Step 4: Ejecutar test para verificar que pasa**

Run: `uv run python -m unittest tests.test_gemini -v`
Expected: PASS (4 tests)

---

### Task 3: Crear módulo answers.py - Lógica de posiciones de respuestas

**Files:**
- Create: `src/hakunamatata/answers.py`
- Test: `tests/test_answers.py`

**Step 1: Escribir el test que falla**

```python
import unittest

from hakunamatata.answers import (
    calcular_posiciones_opciones,
    PosicionOpcion,
)


class TestAnswers(unittest.TestCase):
    def test_calcula_cuatro_opciones_en_columna(self):
        posiciones = calcular_posiciones_opciones(1920, 1080, 4)
        self.assertEqual(len(posiciones), 4)

    def test_posiciones_espaciadas_verticalmente(self):
        posiciones = calcular_posiciones_opciones(1920, 1080, 4)
        for i in range(1, len(posiciones)):
            self.assertGreater(
                posiciones[i].y,
                posiciones[i - 1].y,
            )

    def test_opcion_central_esta_en_medio_de_la_pantalla(self):
        posiciones = calcular_posiciones_opciones(1920, 1080, 2)
        centro_x = 1920 // 2
        self.assertAlmostEqual(posiciones[0].x, centro_x, delta=200)
```

**Step 2: Ejecutar test para verificar que falla**

Run: `uv run python -m unittest tests.test_answers -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Implementación mínima**

```python
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
        posiciones.append(
            PosicionOpcion(
                x=margen_x,
                y=inicio_y + i * espaciado,
            )
        )
    return posiciones


def marcar_respuesta_correcta(
    posiciones: list[PosicionOpcion],
    indice_correcto: int,
) -> list[PosicionOpcion]:
    for i, p in enumerate(posiciones):
        if i == indice_correcto:
            p.es_correcta = True
    return posiciones
```

**Step 4: Ejecutar test para verificar que pasa**

Run: `uv run python -m unittest tests.test_answers -v`
Expected: PASS (3 tests)

---

### Task 4: Actualizar overlay.py para soportar múltiples círculos

**Files:**
- Modify: `src/hakunamatata/overlay.py`
- Test: `tests/test_overlay_layout.py`

**Step 1: Extender tests existentes**

Agregar al final de `tests/test_overlay_layout.py`:

```python
from hakunamatata.overlay import (
    overlay_opciones,
    PosicionOpcion,
)


class TestOverlayOpciones(unittest.TestCase):
    def test_overlay_opciones_agrupa_por_fila(self):
        opciones = [
            PosicionOpcion(x=10, y=100, es_correcta=True),
            PosicionOpcion(x=10, y=200, es_correcta=False),
        ]
        overlays = overlay_opciones(opciones, alto=1080, origen_y_arriba=True)
        self.assertEqual(len(overlays), 1)
        self.assertEqual(overlays[0].indice_correcto, 0)

    def test_overlay_opciones_filtra_fuera_de_primera_fila(self):
        opciones = [
            PosicionOpcion(x=10, y=500),
            PosicionOpcion(x=10, y=600),
        ]
        overlays = overlay_opciones(opciones, alto=1080, origen_y_arriba=True)
        # Solo los que están en la primera fila (índice 0) se muestran con el mouse arriba
        mouse_y = 10
        visibles = [o for o in overlays if o.y < 1080 // 4]
        self.assertEqual(len(visibles), 0)
```

**Step 2: Ejecutar test para verificar que falla**

Run: `uv run python -m unittest tests.test_overlay_layout.TestOverlayOpciones -v`
Expected: FAIL - import error

**Step 3: Implementar overlay_opciones en overlay.py**

Agregar al final de `overlay.py`:

```python
from dataclasses import dataclass


@dataclass
class PosicionOpcion:
    x: int
    y: int
    tamano: int = 34
    es_correcta: bool = False


@dataclass
class GrupoOverlay:
    posiciones: list[tuple[int, int, int]]  # (x, y, tamano)
    indice_correcto: int
    color_base: str = "#ffffff"
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
    indice_correcto = -1

    altura_fila = alto / filas

    for i, op in enumerate(opciones):
        if not grupo_actual:
            grupo_actual.append(op)
        else:
            if _misma_fila(grupo_actual[0].y, op.y, altura_fila):
                grupo_actual.append(op)
            else:
                grupos.append(_grupo_desde(grupo_actual))
                grupo_actual = [op]
        if op.es_correcta:
            indice_correcto = i

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
        color_base="#cccccc",
        color_correcto="#00ff00",
    )
```

**Step 4: Ejecutar test para verificar que pasa**

Run: `uv run python -m unittest tests.test_overlay_layout.TestOverlayOpciones -v`
Expected: PASS (2 tests)

---

### Task 5: Integrar Gemini en UI macOS

**Files:**
- Modify: `src/hakunamatata/ui/macos.py`

**Step 1: Modificar macos.py**

Importar los nuevos módulos y reemplazar la lógica de cambio de color con el flujo Gemini:

- Cuando se detecta un cambio en la captura (nueva pregunta), enviar captura a Gemini
- Mostrar círculos en las posiciones de las opciones de respuesta
- Resaltar la respuesta correcta

**Step 2: Verificar que tests existentes aún pasan**

Run: `uv run python -m unittest discover -s tests -v`
Expected: PASS

---

### Task 6: Integrar Gemini en UI Windows

**Files:**
- Modify: `src/hakunamatata/ui/windows.py`

**Step 1: Modificar windows.py**

Misma integración que macOS pero con Tkinter:
- Agregar múltiples círculos en el canvas
- Resaltar el círculo correcto
- Llamar a Gemini cuando cambie la captura

**Step 2: Verificar que tests existentes aún pasan**

Run: `uv run python -m unittest discover -s tests -v`
Expected: PASS

---

### Task 7: Entrypoint y configuración

**Files:**
- Modify: `punto_rojo.py`

**Step 1: Agregar carga de API key y cliente compartido**

```python
from hakunamatata.gemini import crear_cliente

cliente = crear_cliente()
```

El cliente se pasa a las UI para que lo usen.

**Step 2: Verificar lint**

Run: `uv run python -m unittest discover -s tests -v`
Expected: PASS
