import unittest

from hakunamatata.detection import color_desde_paso, crear_huella_visual, debe_cambiar_color
from hakunamatata.overlay import calcular_punto, debe_mostrarse_circulo, obtener_indice_fila_vertical
from punto_rojo import EstadoDeteccion, actualizar_estado, ocultar_region


class TestOverlayLayout(unittest.TestCase):
    def test_calcula_punto_en_windows(self):
        punto = calcular_punto(1920, 1080, origen_y_arriba=True)

        self.assertEqual(punto, (20, 1026, 34))

    def test_calcula_punto_en_macos(self):
        punto = calcular_punto(1920, 1080, origen_y_arriba=False)

        self.assertEqual(punto, (20, 20, 34))

    def test_obtener_indice_fila_vertical_divide_en_cuatro(self):
        self.assertEqual(obtener_indice_fila_vertical(10, 1080, origen_y_arriba=True), 0)
        self.assertEqual(obtener_indice_fila_vertical(300, 1080, origen_y_arriba=True), 1)
        self.assertEqual(obtener_indice_fila_vertical(600, 1080, origen_y_arriba=True), 2)
        self.assertEqual(obtener_indice_fila_vertical(1079, 1080, origen_y_arriba=True), 3)

    def test_debe_mostrarse_circulo_solo_en_la_primera_fila(self):
        self.assertTrue(debe_mostrarse_circulo(10, 1080, origen_y_arriba=True))
        self.assertFalse(debe_mostrarse_circulo(300, 1080, origen_y_arriba=True))


class TestMonitorLogic(unittest.TestCase):
    def test_debe_cambiar_color_si_similitud_baja(self):
        self.assertTrue(debe_cambiar_color(0.949, 0.95))

    def test_no_debe_cambiar_color_si_similitud_alta(self):
        self.assertFalse(debe_cambiar_color(0.96, 0.95))

    def test_actualiza_color_si_captura_cambia(self):
        estado = EstadoDeteccion(anterior="aaaa", color_hex="#ff0000")

        cambiado = actualizar_estado(estado, [[1, 1], [1, 2]])

        self.assertTrue(cambiado)
        self.assertNotEqual(estado.color_hex, "#ff0000")

    def test_crear_huella_visual_detecta_un_cambio_pequeno(self):
        imagen_a = [[10] * 32 for _ in range(32)]
        imagen_b = [[10] * 32 for _ in range(32)]
        imagen_b[15][15] = 50

        huella_a = crear_huella_visual(imagen_a)
        huella_b = crear_huella_visual(imagen_b)

        self.assertNotEqual(huella_a, huella_b)

    def test_color_desde_paso_cambia_con_paso_distinto(self):
        color_a = color_desde_paso(0)
        color_b = color_desde_paso(1)

        self.assertNotEqual(color_a, color_b)

    def test_color_desde_paso_es_vivo(self):
        color = color_desde_paso(0)
        rojo = int(color[1:3], 16)
        verde = int(color[3:5], 16)
        azul = int(color[5:7], 16)

        self.assertGreaterEqual(max(rojo, verde, azul), 240)
        self.assertLessEqual(min(rojo, verde, azul), 20)

    def test_ocultar_region_borra_el_punto(self):
        imagen = [[5] * 10 for _ in range(10)]

        ocultar_region(imagen, 2, 2, 3, origen_y_arriba=True)

        self.assertEqual(imagen[2][2], 0)
        self.assertEqual(imagen[4][4], 0)


from hakunamatata.answers import PosicionOpcion
from hakunamatata.overlay import overlay_opciones


class TestOverlayOpciones(unittest.TestCase):
    def test_overlay_opciones_agrupa_misma_fila(self):
        opciones = [
            PosicionOpcion(x=10, y=100, es_correcta=True),
            PosicionOpcion(x=200, y=110, es_correcta=False),
        ]
        grupos = overlay_opciones(opciones, alto=1080, origen_y_arriba=True)
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0].indice_correcto, 0)
        self.assertEqual(len(grupos[0].posiciones), 2)

    def test_overlay_opciones_separa_filas_distintas(self):
        opciones = [
            PosicionOpcion(x=10, y=100),
            PosicionOpcion(x=10, y=500),
        ]
        grupos = overlay_opciones(opciones, alto=1080, origen_y_arriba=True)
        self.assertEqual(len(grupos), 2)

    def test_sin_opciones_devuelve_vacio(self):
        grupos = overlay_opciones([], alto=1080, origen_y_arriba=True)
        self.assertEqual(grupos, [])

    def test_correcto_en_segunda_opcion(self):
        opciones = [
            PosicionOpcion(x=10, y=100, es_correcta=False),
            PosicionOpcion(x=200, y=110, es_correcta=True),
        ]
        grupos = overlay_opciones(opciones, alto=1080, origen_y_arriba=True)
        self.assertEqual(grupos[0].indice_correcto, 1)


if __name__ == "__main__":
    unittest.main()
