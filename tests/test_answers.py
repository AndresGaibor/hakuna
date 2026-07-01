from __future__ import annotations

import unittest

from hakunamatata.answers import PosicionOpcion, calcular_posiciones_opciones, marcar_respuesta_correcta


class TestCalcularPosiciones(unittest.TestCase):
    def test_calcula_cuatro_opciones(self):
        posiciones = calcular_posiciones_opciones(1920, 1080, 4)
        self.assertEqual(len(posiciones), 4)

    def test_posiciones_espaciadas_verticalmente(self):
        posiciones = calcular_posiciones_opciones(1920, 1080, 4)
        for i in range(1, len(posiciones)):
            self.assertGreater(posiciones[i].y, posiciones[i - 1].y)

    def test_opciones_en_margen_izquierdo(self):
        posiciones = calcular_posiciones_opciones(1920, 1080, 2)
        for p in posiciones:
            self.assertEqual(p.x, 40)

    def test_tamano_por_defecto(self):
        posiciones = calcular_posiciones_opciones(1920, 1080, 2)
        for p in posiciones:
            self.assertEqual(p.tamano, 34)

    def test_ninguna_marcada_por_defecto(self):
        posiciones = calcular_posiciones_opciones(1920, 1080, 4)
        for p in posiciones:
            self.assertFalse(p.es_correcta)

    def test_inicio_y_es_proporcional(self):
        posiciones = calcular_posiciones_opciones(1920, 1080, 4)
        esperado_inicio = int(1080 * 0.35)
        self.assertEqual(posiciones[0].y, esperado_inicio)


class TestMarcarRespuesta(unittest.TestCase):
    def test_marca_indice_correcto(self):
        posiciones = [
            PosicionOpcion(x=10, y=100),
            PosicionOpcion(x=10, y=200),
        ]
        resultado = marcar_respuesta_correcta(posiciones, 1)
        self.assertTrue(resultado[1].es_correcta)
        self.assertFalse(resultado[0].es_correcta)

    def test_indice_fuera_de_rango_no_rompe(self):
        posiciones = [PosicionOpcion(x=10, y=100)]
        resultado = marcar_respuesta_correcta(posiciones, 5)
        self.assertFalse(resultado[0].es_correcta)


if __name__ == "__main__":
    unittest.main()
