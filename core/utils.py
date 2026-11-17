"""Utilidades generales de bits, enteros y reducción de imágenes."""

import cv2
import numpy as np


def reducir(img, lado_max=900):
    """Reduce una imagen para que su lado máximo sea lado_max (mantiene aspecto)."""
    h, w = img.shape[:2]
    f = lado_max / max(h, w)
    if f >= 1:
        return img
    return cv2.resize(img, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)


def int_a_bits(v, n):
    """Convierte un entero en un array de n bits (MSB primero)."""
    return np.array([(v >> (n - 1 - i)) & 1 for i in range(n)], dtype=np.uint8)


def bits_a_int(b):
    """Convierte un array de bits en un entero."""
    v = 0
    for x in b:
        v = (v << 1) | int(x)
    return v
