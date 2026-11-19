"""Constantes del protocolo de trama digital."""

# Marca de inicio de trama (16 bits)
MAGIC = 0xA5C3

# Formato legacy (v1): RGB sin comprimir
# magic(16) | ancho(16) | alto(16) | bits/muestra(8) | CRC32(32)
HDR_BITS = 16 + 16 + 16 + 8 + 32

# Formato nuevo (v2): capas R/G/B comprimidas por separado en WebP
MAGIC_CAPAS = 0xA5C4
VERSION_CAPAS = 2
# magic(16) | version(8) | ancho(16) | alto(16) | n_capas(8)
# | bits/muestra(8) | calidad WebP(8) | bytes de payload(32) | CRC32(32)
HDR_BITS_CAPAS = 16 + 8 + 16 + 16 + 8 + 8 + 8 + 32 + 32
