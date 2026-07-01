from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from hakunamatata.capture import _guardar_bytes_debug, _ruta_debug_captura


class TestDebugCaptura(unittest.TestCase):
    def test_ruta_debug_usa_tempdir(self):
        with patch("tempfile.gettempdir", return_value="/tmp/haku-test"):
            ruta = _ruta_debug_captura("haku_capture_raw.bmp")

        self.assertEqual(ruta, "/tmp/haku-test/haku_capture_raw.bmp")

    def test_guardar_bytes_debug_escribe_archivo(self):
        with tempfile.TemporaryDirectory() as dir_temp:
            with patch("tempfile.gettempdir", return_value=dir_temp):
                with patch("hakunamatata.hud.log_hud"):
                    ruta = _guardar_bytes_debug("haku_capture_sent.png", b"abc123")

            self.assertTrue(os.path.exists(ruta))
            with open(ruta, "rb") as f:
                self.assertEqual(f.read(), b"abc123")


if __name__ == "__main__":
    unittest.main()
