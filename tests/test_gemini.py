from __future__ import annotations

import json
import os
import unittest

from hakunamatata.gemini import (
    RespuestaPregunta,
    _leer_api_key_persistida,
    _llamar_modelo,
    _parsear_respuesta_json,
    _persistir_api_key,
    _ruta_config,
    analizar_captura,
    crear_cliente,
)


class TestRespuestaPregunta(unittest.TestCase):
    def test_tiene_respuesta_con_indice_valido(self):
        r = RespuestaPregunta(opciones=["a", "b"], indice_correcto=0)
        self.assertTrue(r.tiene_respuesta())

    def test_sin_respuesta_no_tiene_respuesta(self):
        r = RespuestaPregunta.sin_respuesta()
        self.assertFalse(r.tiene_respuesta())

    def test_opciones_correctas_con_indice_valido(self):
        r = RespuestaPregunta(opciones=["a", "b", "c"], indice_correcto=1)
        self.assertEqual(r.opciones_correctas(), ["b"])

    def test_opciones_correctas_sin_respuesta(self):
        r = RespuestaPregunta.sin_respuesta()
        self.assertEqual(r.opciones_correctas(), [])


class TestPersistenciaApiKey(unittest.TestCase):
    def setUp(self):
        self._ruta = _ruta_config()
        self._existia = os.path.exists(self._ruta)
        if self._existia:
            with open(self._ruta) as f:
                self._contenido_original = f.read()

    def tearDown(self):
        if self._existia:
            os.makedirs(os.path.dirname(self._ruta), exist_ok=True)
            with open(self._ruta, "w") as f:
                f.write(self._contenido_original)
        elif os.path.exists(self._ruta):
            os.remove(self._ruta)

    def test_persistir_y_leer_api_key(self):
        _persistir_api_key("test-key-persistida")
        leida = _leer_api_key_persistida()
        self.assertEqual(leida, "test-key-persistida")

    def test_ruta_config_termina_en_config_json(self):
        self.assertTrue(_ruta_config().endswith("config.json"))

    def test_leer_sin_archivo_devuelve_none(self):
        if os.path.exists(self._ruta):
            os.remove(self._ruta)
        leida = _leer_api_key_persistida()
        self.assertIsNone(leida)

    def test_persistir_crea_directorio(self):
        _persistir_api_key("otra-key")
        self.assertTrue(os.path.exists(self._ruta))


class TestCrearCliente(unittest.TestCase):
    def test_crear_cliente_con_api_key(self):
        cliente = crear_cliente("test-key-123")
        self.assertIsNotNone(cliente)

    def test_crear_cliente_sin_key_usa_variable_entorno(self):
        os.environ["GEMINI_API_KEY"] = "env-key"
        cliente = crear_cliente()
        self.assertIsNotNone(cliente)
        del os.environ["GEMINI_API_KEY"]


class TestParsearRespuesta(unittest.TestCase):
    def test_json_directo(self):
        datos = _parsear_respuesta_json('{"pregunta": "¿X?", "opciones": ["A","B"], "indice_correcto": 0}')
        self.assertIsNotNone(datos)
        self.assertEqual(datos["pregunta"], "¿X?")

    def test_json_con_triple_backtick(self):
        datos = _parsear_respuesta_json("```json\n{\"pregunta\": \"¿Y?\", \"opciones\": [\"1\",\"2\"], \"indice_correcto\": 1}\n```")
        self.assertIsNotNone(datos)
        self.assertEqual(datos["indice_correcto"], 1)

    def test_json_extraido_de_texto(self):
        datos = _parsear_respuesta_json("Aquí está: {\"pregunta\": \"¿Z?\", \"opciones\": [\"X\",\"Y\"], \"indice_correcto\": 0}")
        self.assertIsNotNone(datos)
        self.assertEqual(datos["pregunta"], "¿Z?")

    def test_texto_sin_json(self):
        datos = _parsear_respuesta_json("No encontré ninguna pregunta")
        self.assertIsNone(datos)


class TestLlamarModelo(unittest.TestCase):
    def test_respuesta_valida_retorna_pregunta(self):
        class ClienteMock:
            class models:
                @staticmethod
                def generate_content(model, contents, config=None):
                    class Resp:
                        text = '{"pregunta": "¿2+2?", "opciones": ["3","4","5"], "indice_correcto": 1}'
                    return Resp()

        resultado = _llamar_modelo(ClienteMock(), "gemini-3.5-flash", b"fake")
        self.assertTrue(resultado.tiene_respuesta())
        self.assertEqual(resultado.indice_correcto, 1)
        self.assertEqual(resultado.opciones_correctas(), ["4"])

    def test_respuesta_sin_opciones_retorna_sin_respuesta(self):
        class ClienteMock:
            class models:
                @staticmethod
                def generate_content(model, contents, config=None):
                    class Resp:
                        text = '{"pregunta": "?", "opciones": []}'
                    return Resp()

        resultado = _llamar_modelo(ClienteMock(), "g-model", b"fake")
        self.assertFalse(resultado.tiene_respuesta())


class TestAnalizarCaptura(unittest.TestCase):
    def test_cliente_none_devuelve_sin_respuesta(self):
        resultado = analizar_captura(None, b"")
        self.assertFalse(resultado.tiene_respuesta())

    def test_png_bytes_none_devuelve_sin_respuesta(self):
        resultado = analizar_captura(object(), None)
        self.assertFalse(resultado.tiene_respuesta())


class TestCacheImagen(unittest.TestCase):
    def setUp(self):
        from hakunamatata.cache import _ruta_cache
        self._ruta = _ruta_cache()
        self._existia = os.path.exists(self._ruta)
        if self._existia:
            with open(self._ruta) as f:
                self._contenido_original = f.read()

    def tearDown(self):
        if self._existia:
            os.makedirs(os.path.dirname(self._ruta), exist_ok=True)
            with open(self._ruta, "w") as f:
                f.write(self._contenido_original)
        elif os.path.exists(self._ruta):
            os.remove(self._ruta)

    def test_guardar_y_buscar_por_huella(self):
        from hakunamatata.cache import buscar_por_huella_imagen, guardar_por_huella_imagen, _huella_imagen

        png = b"datos_de_prueba"
        huella = _huella_imagen(png)
        guardar_por_huella_imagen(huella, "¿P?", ["A", "B"], 0)
        resultado = buscar_por_huella_imagen(huella)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["indice_correcto"], 0)

    def test_buscar_huella_inexistente(self):
        from hakunamatata.cache import buscar_por_huella_imagen

        resultado = buscar_por_huella_imagen("no_existe")
        self.assertIsNone(resultado)

    def test_huella_imagen_es_determinista(self):
        from hakunamatata.cache import _huella_imagen

        self.assertEqual(_huella_imagen(b"data"), _huella_imagen(b"data"))
        self.assertNotEqual(_huella_imagen(b"data"), _huella_imagen(b"datN"))


if __name__ == "__main__":
    unittest.main()
