"""Modulación ASK/FSK/PSK, canal ruidoso y demodulación por bit."""

import numpy as np


def modular(bits, esquema, fs, spb):
    """
    Modula un array de bits (0/1) en una señal analógica.

    esquema: "ASK", "FSK" o "PSK".
    fs: frecuencia de muestreo (Hz).
    spb: samples per bit.
    Devuelve la señal modulada como array float64.
    """
    baud = fs / spb
    b = np.repeat(bits.astype(np.float64), spb)
    t = np.arange(len(b)) / fs
    if esquema == "ASK":  # OOK con portadora residual
        s = (0.25 + 0.75 * b) * np.sin(2 * np.pi * 2 * baud * t)
    elif esquema == "FSK":  # 1 ciclo/bit = '0', 2 ciclos/bit = '1', fase continua
        f = np.where(b > 0.5, 2 * baud, baud)
        s = np.sin(2 * np.pi * np.cumsum(f) / fs)
    elif esquema == "PSK":  # BPSK: fase 0 / pi
        s = (2 * b - 1) * np.sin(2 * np.pi * 2 * baud * t)
    else:
        raise ValueError(f"Esquema desconocido: {esquema}")
    return s


def canal(s, snr_db):
    """Añade ruido AWGN si snr_db no es None. Devuelve la señal recibida."""
    if snr_db is None:
        return s
    pot = np.mean(s ** 2)
    sigma = np.sqrt(pot / 10 ** (snr_db / 10))
    return s + np.random.default_rng(0).normal(0, sigma, len(s))


def demodular(x, esquema, fs, spb):
    """
    Demodula la señal recibida recuperando bits.

    Devuelve (bits, estadistico_de_decision, umbral).
    """
    baud = fs / spb
    nb = len(x) // spb
    seg = x[: nb * spb].reshape(nb, spb)
    tl = np.arange(spb) / fs
    if esquema == "ASK":
        est = np.sqrt((seg ** 2).mean(1))
        lo, hi = np.percentile(est, [5, 95])
        umbral = (lo + hi) / 2
        bits = (est > umbral).astype(np.uint8)
    elif esquema == "FSK":
        r0 = np.exp(-2j * np.pi * baud * tl)
        r1 = np.exp(-2j * np.pi * 2 * baud * tl)
        e0, e1 = np.abs(seg @ r0) ** 2, np.abs(seg @ r1) ** 2
        est, umbral = (e1 - e0) / (spb / 2) ** 2, 0.0
        bits = (est > 0).astype(np.uint8)
    elif esquema == "PSK":
        ref = np.sin(2 * np.pi * 2 * baud * tl)
        est, umbral = (seg @ ref) / (spb / 2), 0.0
        bits = (est > 0).astype(np.uint8)
    else:
        raise ValueError(f"Esquema desconocido: {esquema}")
    return bits, est, umbral
