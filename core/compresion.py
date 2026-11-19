"""Separación de la imagen en capas de color y compresión WebP de cada capa.

La imagen se divide en tres capas en escala de grises (R, G y B). Cada capa
se cuantiza al número de bits indicado y se codifica como un archivo WebP
independiente. En recepción las capas se decodifican y se apilan de nuevo
para reconstruir la imagen a color.
"""

import io

import numpy as np
from PIL import Image

FORMATO = "WEBP"
NOMBRES_CAPAS = ("capa_R.webp", "capa_G.webp", "capa_B.webp")


def separar_capas(img_rgb):
    """Devuelve las tres capas de color como arrays uint8 (H, W)."""
    img = np.asarray(img_rgb)
    if img.ndim != 3 or img.shape[2] != 3:
        raise ValueError("Se espera una imagen RGB de forma (H, W, 3).")
    return [np.ascontiguousarray(img[:, :, i]) for i in range(3)]


def cuantizar_capa(capa, nbits):
    """Cuantiza una capa a 2**nbits niveles y la devuelve en el rango 0..255."""
    if not 1 <= nbits <= 8:
        raise ValueError("nbits debe estar entre 1 y 8.")
    niveles = 2 ** nbits
    q = np.round(capa.astype(np.float64) / 255 * (niveles - 1)).astype(np.uint8)
    return np.round(q.astype(np.float64) * 255 / (niveles - 1)).astype(np.uint8)


def comprimir_capa(capa, calidad=85):
    """Comprime una capa en escala de grises a WebP y devuelve sus bytes."""
    if not 1 <= calidad <= 100:
        raise ValueError("La calidad WebP debe estar entre 1 y 100.")
    buf = io.BytesIO()
    Image.fromarray(np.asarray(capa, dtype=np.uint8), mode="L").save(
        buf, format=FORMATO, quality=int(calidad), method=6
    )
    return buf.getvalue()


def comprimir_capas(img_rgb, bits=8, calidad=85):
    """Devuelve (bytes_de_capas, capas_cuantizadas) para R, G y B."""
    capas = separar_capas(img_rgb)
    cuantizadas = [cuantizar_capa(capa, bits) for capa in capas]
    comprimidas = [comprimir_capa(capa, calidad) for capa in cuantizadas]
    return comprimidas, np.stack(cuantizadas, axis=-1)


def descomprimir_capa(datos):
    """Decodifica los bytes de una capa WebP y devuelve un array uint8 (H, W)."""
    try:
        with Image.open(io.BytesIO(datos)) as img:
            return np.asarray(img.convert("L"), dtype=np.uint8)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No se pudo decodificar la capa WebP: {exc}") from exc


def reconstruir_desde_capas(datos_capas, ancho=None, alto=None):
    """Apila las capas decodificadas para reconstruir la imagen RGB."""
    if len(datos_capas) != 3:
        raise ValueError("Se necesitan exactamente 3 capas (R, G, B).")
    canales = []
    for datos in datos_capas:
        capa = descomprimir_capa(datos)
        if ancho and alto and capa.shape != (alto, ancho):
            capa = np.asarray(
                Image.fromarray(capa).resize((ancho, alto)), dtype=np.uint8
            )
        canales.append(capa)
    return np.stack(canales, axis=-1)
