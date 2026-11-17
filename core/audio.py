"""Utilidades de audio: guardado, lectura y sonificación de imágenes."""

import wave

import numpy as np


def guardar_wav(ruta, x, fs):
    """Guarda una señal flotante como WAV PCM 16 bits mono."""
    x = np.asarray(x, dtype=np.float64)
    pico = np.max(np.abs(x)) or 1.0
    pcm = np.int16(np.clip(x / pico, -1, 1) * 32767)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(fs))
        w.writeframes(pcm.tobytes())


def leer_wav(ruta):
    """Lee un WAV y devuelve (señal_float64, fs)."""
    with wave.open(ruta, "rb") as w:
        fs = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return pcm.astype(np.float64) / 32767.0, fs


def sonificar(img, retener):
    """
    Convierte una imagen en señal 1D: escaneo por filas, cada píxel (luminancia) = 1 muestra,
    repetida 'retener' veces para que se escuche.
    """
    lum = img.astype(np.float64) @ np.array([0.299, 0.587, 0.114])
    x = lum.reshape(-1) / 127.5 - 1.0
    return np.repeat(x, retener)
