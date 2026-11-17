"""Constantes del protocolo de trama digital."""

# Marca de inicio de trama (16 bits)
MAGIC = 0xA5C3

# magic(16) | ancho(16) | alto(16) | bits/muestra(8) | CRC32(32)
HDR_BITS = 16 + 16 + 16 + 8 + 32
