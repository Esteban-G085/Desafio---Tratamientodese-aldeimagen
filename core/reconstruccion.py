"""Reconstrucción: guardado PNG/SVG, métricas y figura de comparación."""

import os

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from .audio import sonificar


def guardar_png(img, ruta):
    Image.fromarray(img).save(ruta)


def guardar_svg(img, ruta, escala=8):
    """Guarda la imagen como SVG con rectángulos por runs horizontales de color."""
    h, w, _ = img.shape
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * escala}" height="{h * escala}" '
        f'viewBox="0 0 {w} {h}" shape-rendering="crispEdges">'
    ]
    for y in range(h):
        x = 0
        while x < w:
            c = tuple(int(v) for v in img[y, x])
            x2 = x + 1
            while x2 < w and tuple(int(v) for v in img[y, x2]) == c:
                x2 += 1
            out.append(
                f'<rect x="{x}" y="{y}" width="{x2 - x}" height="1.02" '
                f'fill="rgb({c[0]},{c[1]},{c[2]})"/>'
            )
            x = x2
    out.append("</svg>")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def metricas(a, b):
    """Devuelve (MSE, PSNR) entre dos imágenes."""
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    psnr = float("inf") if mse == 0 else 10 * np.log10(255 ** 2 / mse)
    return mse, psnr


def fig_reconstruccion(referencia, digital, recon, fs, retener, carpeta, nombre,
                       ref_etq="Referencia (filtrada, redimensionada)"):
    """Genera la figura de comparación y devuelve (mse, psnr)."""
    s_ref, s_rec = sonificar(referencia, 1), sonificar(recon, 1)
    mse, psnr = metricas(referencia, recon)
    fig, ax = plt.subplots(2, 3, figsize=(14, 8))
    ax[0, 0].imshow(referencia, interpolation="nearest")
    ax[0, 0].set_title(ref_etq, fontsize=9)
    ax[0, 1].imshow(digital, interpolation="nearest")
    ax[0, 1].set_title("Digital cuantizada (transmitida)", fontsize=9)
    ax[0, 2].imshow(recon, interpolation="nearest")
    ax[0, 2].set_title("Reconstruida tras demodular", fontsize=9)
    for a in ax[0]:
        a.axis("off")
    dif = np.abs(referencia.astype(int) - recon.astype(int)).mean(2)
    im = ax[1, 0].imshow(dif, cmap="inferno", interpolation="nearest")
    ax[1, 0].set_title(f"|diferencia|  MSE={mse:.1f}  PSNR={psnr:.1f} dB", fontsize=9)
    ax[1, 0].axis("off")
    fig.colorbar(im, ax=ax[1, 0], fraction=0.046)
    n = min(400, len(s_ref))
    ax[1, 1].plot(s_ref[:n], label="original", lw=1.2)
    ax[1, 1].plot(s_rec[:n], "--", label="reconstruida", lw=1.0)
    ax[1, 1].set(title="Señal 1D (escaneo por filas): primeras muestras", xlabel="muestra", ylabel="amplitud")
    ax[1, 1].legend(fontsize=8)
    ax[1, 2].plot(s_ref[:n] - s_rec[:n], color="C3")
    ax[1, 2].set(title="Error de reconstrucción", xlabel="muestra")
    fig.suptitle("Etapa 6: comparación gráfica original vs. reconstruida")

    ruta = os.path.join(carpeta, nombre)
    fig.savefig(ruta, dpi=130, bbox_inches="tight")
    print(f"[gráfica] {ruta}")
    plt.close(fig)
    return mse, psnr
