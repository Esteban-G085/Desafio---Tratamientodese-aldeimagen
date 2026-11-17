"""Construcción y parseo de la trama digital (cabecera + payload)."""

import numpy as np
import zlib

from .constantes import MAGIC, HDR_BITS
from .utils import int_a_bits, bits_a_int


def construir_trama(q, nbits):
    """
    Construye la trama completa: cabecera + payload binario.

    q: array (H, W, 3) uint8 con niveles cuantizados.
    nbits: bits por muestra/canal.
    Devuelve (trama_bits, payload_bits) como arrays uint8 de 0/1.
    """
    H, W, _ = q.shape
    # Unpackbits da 8 bits por byte; tomamos los nbits menos significativos
    payload = np.unpackbits(q.reshape(-1, 1), axis=1)[:, 8 - nbits:].reshape(-1)
    crc = zlib.crc32(np.packbits(payload).tobytes()) & 0xFFFFFFFF
    cab = np.concatenate([
        int_a_bits(MAGIC, 16),
        int_a_bits(W, 16),
        int_a_bits(H, 16),
        int_a_bits(nbits, 8),
        int_a_bits(crc, 32),
    ])
    return np.concatenate([cab, payload]).astype(np.uint8), payload


def parsear_trama(bits):
    """
    Parsea una trama recuperada y devuelve (imagen_descuantizada, q, header_info).

    Lanza ValueError si la cabecera es inválida o la trama está incompleta.
    """
    if len(bits) < HDR_BITS or bits_a_int(bits[:16]) != MAGIC:
        raise ValueError("Cabecera inválida: la demodulación no recuperó la marca de trama.")
    W, H = bits_a_int(bits[16:32]), bits_a_int(bits[32:48])
    nbits, crc = bits_a_int(bits[48:56]), bits_a_int(bits[56:88])
    n = W * H * 3 * nbits
    payload = bits[HDR_BITS:HDR_BITS + n]
    if len(payload) < n:
        raise ValueError("Trama incompleta.")
    crc_ok = (zlib.crc32(np.packbits(payload).tobytes()) & 0xFFFFFFFF) == crc
    pesos = 1 << np.arange(nbits - 1, -1, -1)
    q = (payload.reshape(-1, nbits).astype(np.int64) * pesos).sum(1).reshape(H, W, 3).astype(np.uint8)
    return descuantizar_q(q, nbits), q, {"ancho": W, "alto": H, "bits": nbits, "crc_ok": crc_ok}


def descuantizar_q(q, nbits):
    """Convierte niveles cuantizados (0..2^nbits-1) a valores 0..255."""
    return np.round(q.astype(np.float64) * 255 / (2 ** nbits - 1)).astype(np.uint8)
