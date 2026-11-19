"""Construcción y parseo de la trama digital (cabecera + payload)."""

import struct

import numpy as np
import zlib

from .constantes import HDR_BITS, HDR_BITS_CAPAS, MAGIC, MAGIC_CAPAS, VERSION_CAPAS
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


# ---------------------------------------------------------------------- #
#  Trama v2: capas de color comprimidas en WebP
# ---------------------------------------------------------------------- #
def construir_trama_capas(capas_bytes, ancho, alto, bits, calidad):
    """
    Empaqueta las capas WebP en una trama auto-descriptiva (v2).

    Cada capa se precede de su longitud (32 bits, big-endian) para que el
    receptor pueda separarlas aunque vengan concatenadas en un único payload.

    Devuelve (trama_bits, payload_bytes).
    """
    if not capas_bytes:
        raise ValueError("No hay capas para empaquetar.")
    payload = bytearray()
    for blob in capas_bytes:
        datos = bytes(blob)
        payload.extend(struct.pack(">I", len(datos)))
        payload.extend(datos)
    payload = bytes(payload)

    crc = zlib.crc32(payload) & 0xFFFFFFFF
    cab = np.concatenate([
        int_a_bits(MAGIC_CAPAS, 16),
        int_a_bits(VERSION_CAPAS, 8),
        int_a_bits(ancho, 16),
        int_a_bits(alto, 16),
        int_a_bits(len(capas_bytes), 8),
        int_a_bits(bits, 8),
        int_a_bits(int(calidad), 8),
        int_a_bits(len(payload), 32),
        int_a_bits(crc, 32),
    ])
    datos_bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))
    return np.concatenate([cab, datos_bits]).astype(np.uint8), payload


def parsear_trama_capas(bits):
    """
    Parsea una trama v2 y devuelve (lista_de_bytes_webp, header_info).

    Lanza ValueError si la cabecera es inválida, la trama está incompleta o
    las capas no se pueden separar. El campo crc_ok del header permite a la
    GUI informar del resultado de la validación.
    """
    if len(bits) < HDR_BITS_CAPAS or bits_a_int(bits[:16]) != MAGIC_CAPAS:
        raise ValueError("Cabecera v2 inválida: no se encontró la marca de capas WebP.")

    version = bits_a_int(bits[16:24])
    if version != VERSION_CAPAS:
        raise ValueError(f"Versión de trama no soportada: {version}.")

    ancho = bits_a_int(bits[24:40])
    alto = bits_a_int(bits[40:56])
    n_capas = bits_a_int(bits[56:64])
    bits_muestra = bits_a_int(bits[64:72])
    calidad = bits_a_int(bits[72:80])
    total_bytes = bits_a_int(bits[80:112])
    crc = bits_a_int(bits[112:144])

    if not total_bytes or HDR_BITS_CAPAS + total_bytes * 8 > len(bits):
        raise ValueError("Trama v2 incompleta.")

    payload_bits = bits[HDR_BITS_CAPAS:HDR_BITS_CAPAS + total_bytes * 8]
    payload = np.packbits(payload_bits).tobytes()
    crc_ok = (zlib.crc32(payload) & 0xFFFFFFFF) == crc

    header = {
        "version": version,
        "ancho": ancho,
        "alto": alto,
        "n_capas": n_capas,
        "bits": bits_muestra,
        "calidad": calidad,
        "formato": "WEBP",
        "crc_ok": crc_ok,
    }

    try:
        capas = []
        offset = 0
        for _ in range(n_capas):
            if offset + 4 > len(payload):
                raise ValueError("Faltan longitudes de capa en el payload.")
            longitud = struct.unpack_from(">I", payload, offset)[0]
            offset += 4
            if longitud == 0 or offset + longitud > len(payload):
                raise ValueError("Longitud de capa WebP inválida.")
            capas.append(payload[offset:offset + longitud])
            offset += longitud
    except ValueError as exc:
        raise ValueError(
            f"No se pudieron separar las capas (CRC32 {'OK' if crc_ok else 'FALLO'}): {exc}"
        ) from exc

    return capas, header
