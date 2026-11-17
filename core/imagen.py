"""Carga de imagen y filtro de rojo dominante."""

import cv2
import numpy as np
from PIL import Image, ImageOps


def cargar_imagen(ruta):
    """
    Carga una imagen respetando la rotación EXIF y la devuelve como array RGB.

    Devuelve (rgb_array, info_dict) con formato, dpi, alto, ancho.
    """
    im = Image.open(ruta)
    formato = im.format
    dpi = im.info.get("dpi")
    im = ImageOps.exif_transpose(im).convert("RGB")
    rgb = np.array(im)
    info = {
        "formato": formato,
        "dpi": dpi,
        "alto": rgb.shape[0],
        "ancho": rgb.shape[1],
    }
    return rgb, info


def filtrar_rojo_dominante(rgb):
    """
    Mantiene a color la región roja conexa más grande; el resto pasa a grises.

    Devuelve (salida_rgb, mask_bool, rojo_bruto).
    """
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = cv2.split(hsv)
    rojo = (((h <= 10) | (h >= 170)) & (s >= 110) & (v >= 70)).astype(np.uint8) * 255

    k = max(3, rgb.shape[1] // 200) | 1  # kernel impar proporcional
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    rojo = cv2.morphologyEx(rojo, cv2.MORPH_OPEN, ker)
    rojo = cv2.morphologyEx(rojo, cv2.MORPH_CLOSE, ker)

    gris = cv2.cvtColor(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(rojo, connectivity=8)
    if n <= 1:
        print("[aviso] No se detectó rojo; toda la imagen queda en grises.")
        return gris, np.zeros(rojo.shape, bool), rojo

    idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    comp = (etiquetas == idx).astype(np.uint8) * 255
    # Rellenar huecos del contorno externo
    cont, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    relleno = np.zeros_like(comp)
    cv2.drawContours(relleno, cont, -1, 255, thickness=cv2.FILLED)
    mask = relleno > 0

    salida = np.where(mask[..., None], rgb, gris)
    pct = 100 * mask.mean()
    print(f"Región roja dominante: {mask.sum():,} px ({pct:.1f}% de la imagen)")
    return salida, mask, rojo
