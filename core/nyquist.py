"""Análisis espectral espacial y criterio de Nyquist."""

import cv2
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from .utils import reducir


def reportar_frecuencia_muestreo(info, ancho_trabajo, fs_audio, baud):
    """Imprime el reporte de frecuencia de muestreo espacial y temporal."""
    print("=" * 70)
    print("2. FRECUENCIA DE MUESTREO")
    print("=" * 70)
    w, h = info["ancho"], info["alto"]
    print(f"Formato: {info['formato']}   |   Resolución: {w} x {h} px ({w * h / 1e6:.1f} MP)")
    print("Muestreo espacial: 1 muestra por píxel -> fs = 1 px^-1 (Nyquist = 0.5 ciclos/px)")
    if info["dpi"]:
        dx = float(info["dpi"][0])
        print(f"DPI en metadatos: {dx:.0f} -> fs = {dx:.0f} muestras/pulgada = {dx / 25.4:.2f} muestras/mm")
    else:
        print("(La imagen no trae DPI en sus metadatos; se expresa en muestras/píxel.)")
    M = w / ancho_trabajo
    print(f"Para transmitirla se diezma a {ancho_trabajo} px de ancho: factor M = {M:.1f} "
          f"-> fs' = {1 / M:.4f} muestras/px, Nyquist' = {0.5 / M:.4f} ciclos/px")
    print(f"Muestreo temporal del canal: fs_audio = {fs_audio} Hz, tasa de bits = {baud:.0f} bps")
    return M


def analisis_nyquist(gris, mask, M, ancho_trabajo, carpeta, nombre="03_nyquist.png"):
    """Espectro espacial de una fila y muestreo con/sin cumplir Nyquist. Guarda la figura."""
    h, w = gris.shape
    cy = int(np.mean(np.where(mask)[0])) if mask.any() else h // 2
    fila = gris[cy].astype(np.float64)

    x = fila - fila.mean()
    P = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), d=1.0)  # ciclos / píxel
    cum = np.cumsum(P) / P.sum()
    f95 = f[min(np.searchsorted(cum, 0.95), len(f) - 1)]
    nyq_nuevo = 0.5 / M

    print(f"Fila analizada: y = {cy}.  El 95% de la energía espectral llega a {f95:.4f} ciclos/px")
    if f95 > nyq_nuevo:
        print(f"NQS: {f95:.4f} > {nyq_nuevo:.4f} -> con fs' hay riesgo de aliasing; "
              "se aplica filtro antialias (INTER_AREA) antes de diezmar.")
    else:
        print(f"NQS: {f95:.4f} <= {nyq_nuevo:.4f} -> se cumple el criterio de Nyquist.")

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
    ax[0].semilogy(f, P + 1e-9, lw=0.8)
    ax[0].axvline(0.5, color="gray", ls=":", label="Nyquist original (0.5)")
    ax[0].axvline(nyq_nuevo, color="r", ls="--", label=f"Nyquist tras diezmar ({nyq_nuevo:.4f})")
    ax[0].axvline(f95, color="g", ls="-.", label=f"95% energía ({f95:.4f})")
    ax[0].set(title="Espectro espacial de una fila", xlabel="ciclos / píxel", ylabel="potencia")
    ax[0].legend(fontsize=8)

    n_m = 40
    paso = max(int(round(M)), 1)
    ini = max(0, min(w - n_m * paso, int(np.mean(np.where(mask)[1])) - n_m * paso // 2)) if mask.any() else 0
    idx = np.arange(ini, min(ini + n_m * paso, w), paso)
    seg = np.arange(ini, min(ini + n_m * paso, w))
    ax[1].plot(seg, fila[seg], color="0.6", label="señal 'continua' (1 muestra/px)")
    ax[1].stem(idx, fila[idx], linefmt="C1-", markerfmt="C1o", basefmt=" ", label=f"muestreo cada {paso} px")
    ax[1].plot(idx, fila[idx], "C1--", lw=0.8)
    ax[1].set(title="Señal muestreada (NQS)", xlabel="posición x (px)", ylabel="intensidad (0-255)")
    ax[1].legend(fontsize=8)
    fig.suptitle("Etapa 3: muestreo y criterio de Nyquist")

    import os
    ruta = os.path.join(carpeta, nombre)
    fig.savefig(ruta, dpi=130, bbox_inches="tight")
    print(f"[gráfica] {ruta}")
    plt.close(fig)
