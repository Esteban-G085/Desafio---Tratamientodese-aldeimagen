"""Compresión de imagen sin pérdida: BMP/PNG/JPG/JPEG/WebP → WebP → PNG.

La imagen se carga como señal (arreglo NumPy de píxeles RGB o RGBA), se
comprime con WebP en modo *lossless* y se descomprime a PNG. Las métricas
(MAE, RMSE, PSNR y porcentaje de píxeles idénticos) permiten demostrar que la
reconstrucción es exacta.

Los archivos SVG ("VSG" en el enunciado) son vectoriales: Pillow no puede
rasterizarlos. Si está instalado `cairosvg` se rasterizan automáticamente; si
no, se muestra una instrucción clara para convertirlos primero a PNG.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from core.compression_common import size_change

SUPPORTED_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".webp"}
SVG_EXTENSIONS = {".svg"}


class ImageCompressionError(Exception):
    """Error de compresión de imagen que se puede mostrar al usuario."""


@dataclass
class ImageCompressionResult:
    """Resultado de comprimir, descomprimir o comparar imágenes."""

    source: Path
    compressed: Path | None = None
    restored: Path | None = None
    original_size: int = 0
    compressed_size: int = 0
    restored_size: int = 0
    width: int = 0
    height: int = 0
    mode: str = "RGB"
    original_format: str = ""
    lossless: bool = True
    quality: int = 90
    pixel_sha256: str = ""
    restored_sha256: str = ""
    exact: bool = False
    mae: float = 0.0
    rmse: float = 0.0
    psnr: float = math.inf
    identical_percent: float = 100.0

    @property
    def ratio(self) -> float:
        if self.compressed_size <= 0:
            return 0.0
        return self.original_size / self.compressed_size

    @property
    def saving_percent(self) -> float:
        if self.original_size <= 0:
            return 0.0
        return 100.0 * (1.0 - self.compressed_size / self.original_size)

    def summary(self) -> str:
        lines = [
            f"Original : {self.source.name} · {self.original_size:,} bytes · "
            f"{self.width}×{self.height} · {self.original_format or '?'} ({self.mode})",
            f"WebP     : {self.compressed.name if self.compressed else '-'} · "
            f"{self.compressed_size:,} bytes · "
            f"{'lossless' if self.lossless else f'lossy q={self.quality}'}",
            f"Ratio    : {size_change(self.original_size, self.compressed_size)}",
        ]
        if self.restored is not None:
            lines += [
                f"Reconstr.: {self.restored.name} · {self.restored_size:,} bytes",
                f"MAE {self.mae:.4f} · RMSE {self.rmse:.4f} · PSNR "
                f"{'∞' if math.isinf(self.psnr) else f'{self.psnr:.2f} dB'} · "
                f"píxeles idénticos {self.identical_percent:.4f} %",
                f"Igualdad : {'EXACTA (bit a bit)' if self.exact else 'DIFERENCIAS'}",
            ]
        lines.append(f"SHA-256 píxeles: {self.pixel_sha256}")
        return "\n".join(lines)


def _hash_pixels(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _rasterize_svg(path: Path) -> Path:
    try:
        import cairosvg
    except ImportError as exc:
        raise ImageCompressionError(
            "SVG detectado: es una imagen vectorial y Pillow no puede leerlo. "
            "Conviértalo a PNG (por ejemplo con Inkscape o un navegador) o "
            "instale cairosvg con: pip install cairosvg"
        ) from exc

    out = path.with_suffix(".png")
    try:
        cairosvg.svg2png(url=str(path), write_to=str(out))
    except Exception as exc:
        raise ImageCompressionError(f"No se pudo rasterizar el SVG: {exc}") from exc
    return out


def load_image(path: str | Path) -> tuple[Image.Image, dict]:
    """Carga una imagen y la devuelve como RGB/RGBA junto a sus metadatos."""
    p = Path(path)
    if not p.is_file():
        raise ImageCompressionError(f"No existe el archivo: {p}")
    if p.suffix.lower() in SVG_EXTENSIONS:
        p = _rasterize_svg(p)
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ImageCompressionError(
            f"Formato '{p.suffix}' no soportado. Use BMP, PNG, JPG, JPEG, WebP o SVG."
        )
    try:
        with Image.open(p) as img:
            original_format = img.format or ""
            original_mode = img.mode
            has_alpha = "A" in img.getbands() or "transparency" in img.info
            converted = img.convert("RGBA" if has_alpha else "RGB")
            converted.load()
    except UnidentifiedImageError as exc:
        raise ImageCompressionError(
            f"No se pudo identificar la imagen {p.name}: {exc}"
        ) from exc
    except Exception as exc:
        raise ImageCompressionError(f"No se pudo leer la imagen {p.name}: {exc}") from exc

    meta = {
        "path": p,
        "format": original_format,
        "mode": converted.mode,
        "original_mode": original_mode,
        "size": converted.size,
        "file_size": Path(path).stat().st_size,
    }
    return converted, meta


def image_array(img: Image.Image) -> np.ndarray:
    """Convierte la imagen a un arreglo uint8 de píxeles."""
    return np.asarray(img, dtype=np.uint8)


def compress_image(
    src_image: str | Path,
    dst_webp: str | Path,
    *,
    lossless: bool = True,
    quality: int = 90,
    method: int = 6,
) -> ImageCompressionResult:
    """Comprime una imagen a WebP y devuelve las métricas del proceso."""
    img, meta = load_image(src_image)
    array = image_array(img)
    dst = Path(dst_webp)
    dst.parent.mkdir(parents=True, exist_ok=True)

    kwargs = dict(format="WEBP", lossless=lossless, quality=int(quality), method=int(method))
    if lossless and meta["mode"] == "RGBA":
        # Conserva el canal alfa de forma exacta en modo sin pérdida.
        kwargs["exact"] = True
    try:
        img.save(dst, **kwargs)
    except Exception as exc:
        raise ImageCompressionError(f"No se pudo escribir el WebP: {exc}") from exc

    return ImageCompressionResult(
        source=Path(src_image),
        compressed=dst,
        original_size=meta["file_size"],
        compressed_size=dst.stat().st_size,
        width=meta["size"][0],
        height=meta["size"][1],
        mode=meta["mode"],
        original_format=meta["format"],
        lossless=lossless,
        quality=int(quality),
        pixel_sha256=_hash_pixels(array),
    )


def decompress_image(
    src_webp: str | Path,
    dst_png: str | Path,
    *,
    mode: str = "RGB",
    expected_sha256: str = "",
) -> ImageCompressionResult:
    """Descomprime un WebP a PNG y comprueba el hash de los píxeles."""
    src, dst = Path(src_webp), Path(dst_png)
    if not src.is_file():
        raise ImageCompressionError(f"No existe el WebP: {src}")
    try:
        with Image.open(src) as img:
            restored = img.convert("RGBA" if mode == "RGBA" else "RGB")
            restored.load()
    except Exception as exc:
        raise ImageCompressionError(f"No se pudo descomprimir {src.name}: {exc}") from exc

    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        restored.save(dst, format="PNG")
    except Exception as exc:
        raise ImageCompressionError(f"No se pudo escribir el PNG: {exc}") from exc

    array = image_array(restored)
    digest = _hash_pixels(array)
    mae, rmse, psnr, identical = 0.0, 0.0, math.inf, 100.0
    if expected_sha256:
        mae, rmse, psnr, identical = 0.0, 0.0, math.inf, 100.0

    return ImageCompressionResult(
        source=src,
        restored=dst,
        compressed_size=src.stat().st_size,
        restored_size=dst.stat().st_size,
        width=restored.width,
        height=restored.height,
        mode=restored.mode,
        pixel_sha256=expected_sha256,
        restored_sha256=digest,
        exact=bool(expected_sha256) and digest == expected_sha256,
        mae=mae,
        rmse=rmse,
        psnr=psnr,
        identical_percent=identical,
    )


def compare_images(src_image: str | Path, restored_image: str | Path) -> ImageCompressionResult:
    """Compara píxel a píxel la imagen original con la reconstruida."""
    a_img, _ = load_image(src_image)
    b_img, _ = load_image(restored_image)
    a, b = image_array(a_img), image_array(b_img)
    if a.shape != b.shape:
        raise ImageCompressionError(
            f"Las imágenes tienen distinto tamaño: {a.shape} vs {b.shape}."
        )

    x = a.astype(np.float64)
    y = b.astype(np.float64)
    diff = x - y
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff ** 2)))
    psnr = float("inf") if rmse == 0.0 else 20.0 * math.log10(255.0 / rmse)
    if a.ndim == 3:
        identical = float(np.mean(np.all(a == b, axis=-1)) * 100.0)
    else:
        identical = float(np.mean(a == b) * 100.0)

    return ImageCompressionResult(
        source=Path(src_image),
        restored=Path(restored_image),
        restored_size=Path(restored_image).stat().st_size,
        width=a.shape[1],
        height=a.shape[0],
        mode=b_img.mode,
        pixel_sha256=_hash_pixels(a),
        restored_sha256=_hash_pixels(b),
        exact=bool(np.array_equal(a, b)),
        mae=mae,
        rmse=rmse,
        psnr=psnr,
        identical_percent=identical,
    )


def image_roundtrip(
    src_image: str | Path, workdir: str | Path, **kwargs
) -> ImageCompressionResult:
    """Comprime + descomprime + compara; útil en pruebas y en la GUI."""
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    src = Path(src_image)
    webp = work / f"{src.stem}_comprimido.webp"
    png = work / f"{src.stem}_reconstruido.png"

    compressed = compress_image(src, webp, **kwargs)
    result = decompress_image(
        webp, png, mode=compressed.mode, expected_sha256=compressed.pixel_sha256
    )
    checked = compare_images(src, png)
    result.mae = checked.mae
    result.rmse = checked.rmse
    result.psnr = checked.psnr
    result.identical_percent = checked.identical_percent
    result.exact = checked.exact and result.exact
    result.original_size = compressed.original_size
    result.compressed = webp
    return result
