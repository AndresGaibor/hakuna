# Overlay de 4 filas

## Objetivo
Mostrar el circulo solo cuando el mouse esta sobre la primera fila vertical de la pantalla.

## Comportamiento
- La pantalla se divide en 4 filas de igual altura.
- La fila superior activa el circulo.
- Las otras 3 filas ocultan el circulo.

## Implementacion
- `src/hakunamatata/overlay.py` contiene la logica pura para calcular la fila y decidir visibilidad.
- `src/hakunamatata/mouse.py` abstrae la lectura de la posicion del mouse por plataforma.
- `src/hakunamatata/ui/macos.py` y `src/hakunamatata/ui/windows.py` muestran u ocultan el overlay segun la fila activa.

## Verificacion
- `uv run python -m unittest discover -s tests`

## Nota
- La medicion de cobertura quedo pendiente porque `coverage` no esta instalado en el entorno virtual actual.
