"""Pruebas de la compresión de imagen WebP lossless → PNG."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

# El paquete `core` importa el pipeline (que usa cv2) en su __init__.
# Estas pruebas solo ejercitan la compresión de imagen, que no depende de cv2:
# si no está instalado, se registra un módulo mínimo para poder importar `core`.
try:  # pragma: no cover - solo depende del entorno
    import cv2  # noqa: F401
except ImportError:  # pragma: no cover
    cv2_stub = types.ModuleType("cv2")
    cv2_stub.__getattr__ = lambda name: None  # type: ignore[attr-defined]
    sys.modules.setdefault("cv2", cv2_stub)

from core.compression_common import size_change
from core.compression_image import (
    ImageCompressionError, compare_images, image_roundtrip,
)


def make_image(path: Path, height: int = 24, width: int = 32,
               *, alpha: bool = False, seed: int = 7) -> np.ndarray:
    """Crea una imagen determinista en disco y devuelve su arreglo."""
    rng = np.random.default_rng(seed)
    shape = (height, width, 4 if alpha else 3)
    arr = rng.integers(0, 256, shape, dtype=np.uint8)
    if alpha:
        arr[..., 3] = rng.integers(0, 256, (height, width), dtype=np.uint8)
    Image.fromarray(arr).save(path)
    return arr


class CompressionImageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_roundtrip_rgb_exacto(self) -> None:
        src = self.tmp / "rgb.png"
        make_image(src)
        result = image_roundtrip(src, self.tmp / "salida_rgb")
        self.assertTrue(result.exact)
        self.assertEqual(result.mae, 0.0)
        self.assertEqual(result.rmse, 0.0)
        self.assertEqual(result.identical_percent, 100.0)
        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.pixel_sha256, result.restored_sha256)
        self.assertTrue((self.tmp / "salida_rgb" / "rgb_comprimido.webp").is_file())
        self.assertTrue((self.tmp / "salida_rgb" / "rgb_reconstruido.png").is_file())

    def test_roundtrip_rgba_con_transparencia_exacto(self) -> None:
        src = self.tmp / "rgba.png"
        make_image(src, alpha=True)
        result = image_roundtrip(src, self.tmp / "salida_rgba")
        self.assertTrue(result.exact)
        self.assertEqual(result.mode, "RGBA")
        self.assertEqual(result.pixel_sha256, result.restored_sha256)

    def test_extension_no_soportada_se_rechaza(self) -> None:
        src = self.tmp / "ok.png"
        make_image(src)
        bad = self.tmp / "mal.gif"
        bad.write_bytes(b"GIF89a")
        with self.assertRaises(ImageCompressionError):
            compare_images(src, bad)

    def test_comparar_imagenes_distinto_tamano(self) -> None:
        a = self.tmp / "a.png"
        b = self.tmp / "b.png"
        make_image(a, 16, 16)
        make_image(b, 20, 20)
        with self.assertRaises(ImageCompressionError):
            compare_images(a, b)

    def test_size_change_cuando_el_archivo_crece(self) -> None:
        texto = size_change(1000, 1400)
        self.assertIn("40.0 % más grande", texto)
        self.assertIn("0.71×", texto)


if __name__ == "__main__":
    unittest.main()
