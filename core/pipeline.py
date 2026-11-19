"""
Pipeline completo de procesamiento de señal de imagen.

Orquestador que une: carga, filtro rojo, Nyquist, cuantización,
construcción de trama, modulación, canal, demodulación y reconstrucción.

Diseñado para ser usado tanto desde CLI como desde GUI mediante
un callback de progreso.
"""

import json
import os
import zipfile

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .audio import guardar_wav, leer_wav, sonificar
from .compresion import comprimir_capas, reconstruir_desde_capas
from .constantes import HDR_BITS
from .imagen import cargar_imagen, filtrar_rojo_dominante
from .modulacion import canal, demodular, modular
from .nyquist import analisis_nyquist, reportar_frecuencia_muestreo
from .reconstruccion import fig_reconstruccion, guardar_png, guardar_svg, metricas
from .trama import (
    construir_trama,
    construir_trama_capas,
    parsear_trama,
    parsear_trama_capas,
)
from .utils import bits_a_int, int_a_bits


class ImageSignalPipeline:
    """
    Ejecuta el pipeline de desafío 4.

    progress_callback: función opcional(stage: str, message: str, percent: float)
    """

    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback

    def _progreso(self, stage, message, percent=0.0):
        if self.progress_callback:
            self.progress_callback(stage, message, percent)

    # ------------------------------------------------------------------ #
    #  Modo ENVÍO: procesar foto -> paquete ZIP
    # ------------------------------------------------------------------ #
    def run_send(self, foto_path, salida, mod="FSK", bits=8, ancho=64,
                 fs=44100, baud=4410.0, snr=None, reproducir_audio=False,
                 mostrar_graficas=True, escuchar_seg=8, retener=10,
                 calidad_webp=85, flujo="ambos"):
        """
        Ejecuta etapas 1-6 y devuelve un dict con rutas, imágenes y métricas.

        calidad_webp: calidad de compresión de cada capa (1-100).
        flujo: "wav" (señal modulada), "directo" (solo WebP) o "ambos".
        """
        os.makedirs(salida, exist_ok=True)
        spb = int(round(fs / baud))
        if spb < 8:
            raise ValueError("baud demasiado alto para fs: usa baud <= fs/8")
        baud_real = fs / spb

        # ---- 1/2. Carga y filtro ------------------------------------- #
        self._progreso("carga", "Cargando imagen y aplicando filtro de rojo dominante...", 5)
        rgb, info = cargar_imagen(foto_path)
        filtrada, mask, rojo_bruto = filtrar_rojo_dominante(rgb)

        fig, ax = plt.subplots(1, 3, figsize=(15, 5))
        ax[0].imshow(self._reducir_para_mostrar(rgb))
        ax[0].set_title("Original a color")
        ax[1].imshow(self._reducir_para_mostrar(mask.astype(np.uint8) * 255), cmap="gray")
        ax[1].set_title("Máscara: rojo dominante")
        ax[2].imshow(self._reducir_para_mostrar(filtrada))
        ax[2].set_title("Solo el rojo de mayor área (resto en grises)")
        for p in ax:
            p.axis("off")
        ruta_fig02 = os.path.join(salida, "02_original_y_filtro.png")
        fig.savefig(ruta_fig02, dpi=130, bbox_inches="tight")
        plt.close(fig)
        ruta_filtrada = os.path.join(salida, "02_imagen_filtrada.png")
        guardar_png(filtrada, ruta_filtrada)

        # ---- 3. Muestreo y Nyquist ----------------------------------- #
        self._progreso("nyquist", "Análisis de Nyquist y muestreo espacial...", 20)
        M = reportar_frecuencia_muestreo(info, ancho, fs, baud_real)
        gris_full = cv2.cvtColor(filtrada, cv2.COLOR_RGB2GRAY)
        ruta_nyq = os.path.join(salida, "03_nyquist.png")
        analisis_nyquist(gris_full, mask, M, ancho, salida, nombre="03_nyquist.png")

        alto = max(1, int(round(info["alto"] * ancho / info["ancho"])))
        pequena = cv2.resize(filtrada, (ancho, alto), interpolation=cv2.INTER_AREA)
        self._progreso("capas", "Separando en capas R/G/B y comprimiendo a WebP...", 30)
        capas_bytes, capas_cuantizadas = comprimir_capas(pequena, bits, calidad_webp)
        digital = reconstruir_desde_capas(capas_bytes, ancho, alto)
        trama, payload = construir_trama_capas(capas_bytes, ancho, alto, bits, calidad_webp)

        nombres_capas = ["capa_R.webp", "capa_G.webp", "capa_B.webp"][:len(capas_bytes)]
        rutas_capas = []
        for nombre, blob in zip(nombres_capas, capas_bytes):
            ruta_capa = os.path.join(salida, nombre)
            with open(ruta_capa, "wb") as f:
                f.write(blob)
            rutas_capas.append(ruta_capa)

        tam_webp = sum(len(blob) for blob in capas_bytes)
        self._progreso(
            "trama",
            f"Trama v2: {len(trama):,} bits | {len(capas_bytes)} capas WebP, {tam_webp:,} bytes",
            35,
        )

        ruta_bin = os.path.join(salida, "03_digital.bin")
        with open(ruta_bin, "wb") as f:
            f.write(np.packbits(trama).tobytes())
        with open(os.path.join(salida, "03_digital_bits.txt"), "w") as f:
            f.write("".join(map(str, trama.tolist())))

        cuant_visual = self._descuantizar(capas_cuantizadas, bits)
        fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
        fila = pequena[alto // 2, :, 0]
        ax[0].stem(fila, linefmt="C0-", markerfmt="C0.", basefmt=" ", label="muestreada (8 bit)")
        ax[0].step(range(len(fila)), cuant_visual[alto // 2, :, 0], where="mid", color="C1",
                   label=f"cuantizada ({bits} bit)")
        ax[0].set(title="Fila central, canal R: señal muestreada y cuantizada", xlabel="n", ylabel="valor")
        ax[0].legend(fontsize=8)
        ax[1].hist(capas_cuantizadas.reshape(-1), bins=np.arange(2 ** bits + 1) - 0.5, color="C2")
        ax[1].set(title=f"Histograma de {2 ** bits} niveles", xlabel="nivel", ylabel="muestras")
        ax[2].imshow(digital, interpolation="nearest")
        ax[2].axis("off")
        ax[2].set_title("Imagen digital (capas WebP)")
        fig.suptitle("Etapa 3: capas RGB, cuantización y compresión WebP")
        ruta_dig = os.path.join(salida, "03_digitalizacion.png")
        fig.savefig(ruta_dig, dpi=130, bbox_inches="tight")
        plt.close(fig)

        # ---- 4. Modulación ------------------------------------------- #
        self._progreso("modulacion", f"Modulando ({mod}) a {baud_real:.0f} bps...", 50)
        s = modular(trama, mod, fs, spb)
        dur = len(s) / fs
        self._progreso("modulacion", f"{len(trama):,} bits -> {dur:.1f} s de audio", 55)
        ruta_mod = os.path.join(salida, "04_senal_modulada.wav")
        guardar_wav(ruta_mod, s, fs)

        nz = 50 if mod != "ASK" else 40
        ini = HDR_BITS
        fig, ax = plt.subplots(3, 1, figsize=(13, 9))
        bz = trama[ini:ini + nz]
        ax[0].step(np.arange(nz + 1), np.r_[bz, bz[-1]], where="post", color="k")
        ax[0].set(title=f"Bits de datos (n={ini}..{ini + nz}) - banda base", ylim=(-0.2, 1.3))
        tz = np.arange(nz * spb) / fs * 1000
        ax[1].plot(tz, s[ini * spb:(ini + nz) * spb], lw=0.9)
        ax[1].set(title=f"Señal {mod} (zoom)", xlabel="ms", ylabel="amplitud")
        N = min(len(s), 2 ** 18)
        S = np.abs(np.fft.rfft(s[:N] * np.hanning(N)))
        ax[2].plot(np.fft.rfftfreq(N, 1 / fs), 20 * np.log10(S / S.max() + 1e-6))
        ax[2].set(title=f"Espectro de la señal {mod}", xlabel="Hz", ylabel="dB", xlim=(0, fs / 2), ylim=(-80, 3))
        fig.suptitle("Etapa 4: modulación")
        fig.tight_layout()
        ruta_mod_fig = os.path.join(salida, "04_modulacion.png")
        fig.savefig(ruta_mod_fig, dpi=130, bbox_inches="tight")
        plt.close(fig)

        # ---- Canal + 5. Demodulación --------------------------------- #
        self._progreso("canal", "Aplicando canal ruidoso y demodulando...", 65)
        rx = canal(s, snr)
        meta = {
            "version": 2,
            "flujo": "wav",
            "formato": "WEBP",
            "calidad": calidad_webp,
            "capas": nombres_capas,
            "esquema": mod,
            "fs": fs,
            "spb": spb,
            "baud": baud_real,
            "snr_db": snr,
        }
        bits_rec, est, umbral, img_rec, capas_rec, h = self._demodular_y_reconstruir_capas(
            rx, meta, salida, reproducir_audio, escuchar_seg, retener, fs)

        errores = int(np.sum(bits_rec[:len(trama)] != trama))
        ber = errores / len(trama)
        self._progreso("demodulacion", f"Errores de bit: {errores} de {len(trama):,} (BER = {ber:.2e})", 75)

        nzb = 160
        fig, ax = plt.subplots(3, 1, figsize=(13, 9))
        ax[0].plot(est[ini:ini + nzb], ".-", ms=4)
        ax[0].axhline(umbral, color="r", ls="--", label="umbral de decisión")
        ax[0].set(title=f"Estadístico de decisión por bit ({mod})", xlabel="bit")
        ax[0].legend(fontsize=8)
        ax[1].step(range(nzb), trama[ini:ini + nzb], where="post", label="transmitidos")
        ax[1].step(range(nzb), bits_rec[ini:ini + nzb] + 0.0, where="post", ls="--", label="demodulados")
        ax[1].set(title="Bits (banda base) recuperados", ylim=(-0.2, 1.3), xlabel="bit")
        ax[1].legend(fontsize=8)
        tz2 = np.arange(nzb * spb) / fs * 1000
        ax[2].plot(tz2, rx[ini * spb:(ini + nzb) * spb], lw=0.9, color="C3")
        ax[2].set(title="Señal recibida (zoom)", xlabel="ms")
        fig.suptitle("Etapa 5: demodulación")
        fig.tight_layout()
        ruta_dem_fig = os.path.join(salida, "05_demodulacion.png")
        fig.savefig(ruta_dem_fig, dpi=130, bbox_inches="tight")
        plt.close(fig)

        # Audios de comparación
        s_orig = sonificar(digital, retener)
        s_demo = sonificar(img_rec, retener)
        ruta_audio_demo = os.path.join(salida, "05_demodulada_audio.wav")
        ruta_audio_orig = os.path.join(salida, "06_original_audio.wav")
        guardar_wav(ruta_audio_demo, s_demo, fs)
        guardar_wav(ruta_audio_orig, s_orig, fs)

        # ---- 6. Reconstrucción -------------------------------------- #
        self._progreso("reconstruccion", "Generando PNG, SVG y comparación...", 85)
        ruta_png = os.path.join(salida, "06_reconstruida.png")
        ruta_svg = os.path.join(salida, "06_reconstruida.svg")
        guardar_png(img_rec, ruta_png)
        guardar_svg(img_rec, ruta_svg)

        mse, psnr = fig_reconstruccion(pequena, digital, img_rec, fs, retener, salida, "06_comparacion.png")
        mse2, _ = metricas(digital, img_rec)

        # ---- Paquetes para el compañero ------------------------------ #
        self._progreso("zip", "Empaquetando los paquetes para el compañero...", 95)
        zip_path = os.path.join(salida, "paquete_para_companero.zip")
        zip_directo = os.path.join(salida, "paquete_comprimido.zip")

        if flujo in ("wav", "ambos"):
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
                z.write(ruta_mod, "senal_modulada.wav")
                z.writestr("meta.json", json.dumps(meta, indent=2))
        else:
            zip_path = None

        if flujo in ("directo", "ambos"):
            meta_directo = {
                "version": 2,
                "flujo": "directo",
                "formato": "WEBP",
                "calidad": calidad_webp,
                "capas": nombres_capas,
                "ancho": ancho,
                "alto": alto,
                "bits": bits,
            }
            with zipfile.ZipFile(zip_directo, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
                for nombre, ruta_capa in zip(nombres_capas, rutas_capas):
                    z.write(ruta_capa, nombre)
                z.writestr("meta.json", json.dumps(meta_directo, indent=2))
        else:
            zip_directo = None

        tam_wav = os.path.getsize(ruta_mod)
        tam_zip = os.path.getsize(zip_path) if zip_path else 0
        tam_zip_directo = os.path.getsize(zip_directo) if zip_directo else 0

        self._progreso("fin", "Proceso completado.", 100)

        return {
            "salida": salida,
            "ruta_png": ruta_png,
            "ruta_svg": ruta_svg,
            "ruta_zip": zip_path,
            "ruta_zip_directo": zip_directo,
            "rutas_capas": rutas_capas,
            "flujo": flujo,
            "header": h,
            "ruta_mod_wav": ruta_mod,
            "ruta_audio_demo": ruta_audio_demo,
            "ruta_audio_orig": ruta_audio_orig,
            "ruta_filtrada": ruta_filtrada,
            "ruta_nyq": ruta_nyq,
            "ruta_dig": ruta_dig,
            "ruta_mod_fig": ruta_mod_fig,
            "ruta_dem_fig": ruta_dem_fig,
            "imagen_original": rgb,
            "imagen_filtrada": filtrada,
            "imagen_digital": digital,
            "imagen_reconstruida": img_rec,
            "meta": meta,
            "mse": mse,
            "psnr": psnr,
            "mse_digital_vs_recon": mse2,
            "errores_bit": errores,
            "ber": ber,
            "tam_wav_mb": tam_wav / 1e6,
            "tam_zip_mb": tam_zip / 1e6,
            "tam_zip_directo_kb": tam_zip_directo / 1e3,
            "tam_webp_kb": tam_webp / 1e3,
            "calidad_webp": calidad_webp,
            "duracion_s": dur,
        }

    # ------------------------------------------------------------------ #
    #  Modo RECEPCIÓN: compañero desempaqueta ZIP y demodula
    # ------------------------------------------------------------------ #
    def run_receive(self, paquete_zip, salida, reproducir_audio=False,
                    mostrar_graficas=True, escuchar_seg=8, retener=10, flujo="auto"):
        """
        Detecta el tipo de paquete y reconstruye la imagen.

        flujo: "auto" (lo deduce del ZIP), "wav" (señal modulada) o "directo" (WebP).
        Se mantiene compatibilidad con paquetes antiguos sin comprimir (v1).
        """
        os.makedirs(salida, exist_ok=True)
        with zipfile.ZipFile(paquete_zip) as z:
            nombres = z.namelist()
            meta = json.loads(z.read("meta.json"))

        if flujo not in ("wav", "directo"):
            if meta.get("flujo") in ("wav", "directo"):
                flujo = meta["flujo"]
            else:
                flujo = "wav" if "senal_modulada.wav" in nombres else "directo"

        if flujo == "directo":
            return self.run_receive_directo(paquete_zip, salida, meta=meta)
        if meta.get("version", 1) == 1:
            return self._run_receive_legacy(
                paquete_zip, salida, meta, reproducir_audio, escuchar_seg, retener
            )

        # ---- v2 WAV: capas WebP dentro de la señal modulada ---------- #
        self._progreso("carga", "Extrayendo paquete recibido...", 10)
        with zipfile.ZipFile(paquete_zip) as z:
            z.extract("senal_modulada.wav", salida)

        x, fs = leer_wav(os.path.join(salida, "senal_modulada.wav"))
        esquema = meta["esquema"]
        spb = meta["spb"]
        self._progreso("info", f"Recepción: {esquema} a {meta['baud']:.0f} bps, fs = {fs} Hz", 20)

        meta_completa = dict(meta)
        meta_completa["fs"] = fs
        bits_rec, est, umbral, img, capas_rec, h = self._demodular_y_reconstruir_capas(
            x, meta_completa, salida, reproducir_audio, escuchar_seg, retener, fs)

        s_demo = sonificar(img, retener)
        ruta_audio = os.path.join(salida, "demodulada_audio.wav")
        guardar_wav(ruta_audio, s_demo, fs)
        ruta_png = os.path.join(salida, "recuperada.png")
        ruta_svg = os.path.join(salida, "recuperada.svg")
        guardar_png(img, ruta_png)
        guardar_svg(img, ruta_svg)

        fig, ax = plt.subplots(1, 2, figsize=(12, 5))
        ax[0].imshow(img, interpolation="nearest")
        ax[0].set_title("Imagen recuperada (capas WebP)")
        ax[0].axis("off")
        ax[1].plot(est[HDR_BITS:HDR_BITS + 200], ".-")
        ax[1].axhline(umbral, color="r", ls="--")
        ax[1].set_title("Estadístico de decisión (primeros bits de datos)")
        ruta_analisis = os.path.join(salida, "recuperada_analisis.png")
        fig.savefig(ruta_analisis, dpi=130, bbox_inches="tight")
        plt.close(fig)

        self._progreso("fin", "Recepción completada.", 100)
        return {
            "salida": salida,
            "imagen_recuperada": img,
            "ruta_png": ruta_png,
            "ruta_svg": ruta_svg,
            "ruta_audio": ruta_audio,
            "ruta_analisis": ruta_analisis,
            "meta": meta_completa,
            "header": h,
            "flujo": "wav",
            "capas_recuperadas": capas_rec,
        }

    def run_receive_directo(self, paquete_zip, salida, meta=None):
        """Reconstruye la imagen a partir de un ZIP con las 3 capas WebP."""
        os.makedirs(salida, exist_ok=True)
        self._progreso("carga", "Extrayendo capas WebP comprimidas...", 15)
        with zipfile.ZipFile(paquete_zip) as z:
            if meta is None:
                meta = json.loads(z.read("meta.json"))
            nombres = meta.get("capas") or [n for n in z.namelist() if n.lower().endswith(".webp")]
            if len(nombres) != 3:
                raise ValueError("El paquete directo debe contener 3 capas WebP (R, G, B).")
            capas_bytes = [z.read(nombre) for nombre in nombres]

        ancho, alto = meta.get("ancho"), meta.get("alto")
        img = reconstruir_desde_capas(capas_bytes, ancho, alto)
        self._progreso(
            "reconstruccion",
            f"Capas decodificadas y apiladas: {img.shape[1]}x{img.shape[0]} px",
            60,
        )

        ruta_png = os.path.join(salida, "recuperada.png")
        ruta_svg = os.path.join(salida, "recuperada.svg")
        guardar_png(img, ruta_png)
        guardar_svg(img, ruta_svg)

        fig, ax = plt.subplots(1, 4, figsize=(15, 4))
        for eje, capa, titulo in zip(ax[:3], (img[:, :, 0], img[:, :, 1], img[:, :, 2]), ("R", "G", "B")):
            eje.imshow(capa, cmap="gray", vmin=0, vmax=255)
            eje.set_title(f"Capa {titulo}")
            eje.axis("off")
        ax[3].imshow(img)
        ax[3].set_title("Imagen reconstruida")
        ax[3].axis("off")
        fig.suptitle("Recepción directa: descompresión WebP de las capas")
        ruta_analisis = os.path.join(salida, "recuperada_analisis.png")
        fig.savefig(ruta_analisis, dpi=130, bbox_inches="tight")
        plt.close(fig)

        self._progreso("fin", "Recepción directa completada.", 100)
        return {
            "salida": salida,
            "imagen_recuperada": img,
            "ruta_png": ruta_png,
            "ruta_svg": ruta_svg,
            "ruta_audio": None,
            "ruta_analisis": ruta_analisis,
            "meta": meta,
            "header": {
                "ancho": img.shape[1],
                "alto": img.shape[0],
                "bits": meta.get("bits"),
                "n_capas": 3,
                "formato": "WEBP",
                "crc_ok": True,
            },
            "flujo": "directo",
            "tam_webp_kb": sum(len(c) for c in capas_bytes) / 1e3,
        }

    def _run_receive_legacy(self, paquete_zip, salida, meta, reproducir_audio,
                            escuchar_seg, retener):
        """Mantiene la recepción de paquetes v1 (RGB sin comprimir)."""
        self._progreso("carga", "Extrayendo paquete recibido (formato v1)...", 10)
        with zipfile.ZipFile(paquete_zip) as z:
            z.extract("senal_modulada.wav", salida)

        x, fs = leer_wav(os.path.join(salida, "senal_modulada.wav"))
        esquema, spb = meta["esquema"], meta["spb"]
        self._progreso("info", f"Recepción v1: {esquema} a {meta['baud']:.0f} bps, fs = {fs} Hz", 20)

        meta_completa = {"version": 1, "esquema": esquema, "fs": fs, "spb": spb,
                         "baud": meta["baud"], "snr_db": meta.get("snr_db")}
        bits_rec, est, umbral, img, q, h = self._demodular_y_reconstruir(
            x, meta_completa, salida, reproducir_audio, escuchar_seg, retener, fs)

        s_demo = sonificar(img, retener)
        ruta_audio = os.path.join(salida, "demodulada_audio.wav")
        guardar_wav(ruta_audio, s_demo, fs)
        ruta_png = os.path.join(salida, "recuperada.png")
        ruta_svg = os.path.join(salida, "recuperada.svg")
        guardar_png(img, ruta_png)
        guardar_svg(img, ruta_svg)

        fig, ax = plt.subplots(1, 2, figsize=(12, 5))
        ax[0].imshow(img, interpolation="nearest")
        ax[0].set_title("Imagen recuperada (v1)")
        ax[0].axis("off")
        ax[1].plot(est[HDR_BITS:HDR_BITS + 200], ".-")
        ax[1].axhline(umbral, color="r", ls="--")
        ax[1].set_title("Estadístico de decisión (primeros bits de datos)")
        ruta_analisis = os.path.join(salida, "recuperada_analisis.png")
        fig.savefig(ruta_analisis, dpi=130, bbox_inches="tight")
        plt.close(fig)

        self._progreso("fin", "Recepción completada.", 100)
        return {
            "salida": salida,
            "imagen_recuperada": img,
            "ruta_png": ruta_png,
            "ruta_svg": ruta_svg,
            "ruta_audio": ruta_audio,
            "ruta_analisis": ruta_analisis,
            "meta": meta_completa,
            "header": h,
            "flujo": "wav",
        }

    # ------------------------------------------------------------------ #
    #  Helpers internos
    # ------------------------------------------------------------------ #
    @staticmethod
    def _cuantizar(img, nbits):
        L = 2 ** nbits
        return np.round(img.astype(np.float64) / 255 * (L - 1)).astype(np.uint8)

    @staticmethod
    def _descuantizar(q, nbits):
        return np.round(q.astype(np.float64) * 255 / (2 ** nbits - 1)).astype(np.uint8)

    @staticmethod
    def _reducir_para_mostrar(img, lado_max=900):
        """Reduce una imagen solo para mostrarla en pantalla (sin modificar la original)."""
        import cv2
        h, w = img.shape[:2]
        f = lado_max / max(h, w)
        if f >= 1:
            return img
        return cv2.resize(img, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)

    def _demodular_y_reconstruir(self, x, meta, carpeta, reproducir_audio, max_seg,
                                 retener, fs):
        esquema, spb = meta["esquema"], meta["spb"]
        self._progreso("demodulacion", f"Demodulando ({esquema})...", 70)
        bits_rec, est, umbral = demodular(x, esquema, fs, spb)
        self._progreso("demodulacion", f"{len(bits_rec):,} bits recuperados", 72)
        img, q, h = parsear_trama(bits_rec)
        crc_txt = "OK" if h["crc_ok"] else "FALLO"
        self._progreso("demodulacion",
                       f"Cabecera: {h['ancho']}x{h['alto']} px, {h['bits']} bits/canal, CRC32 {crc_txt}", 74)
        return bits_rec, est, umbral, img, q, h

    def _demodular_y_reconstruir_capas(self, x, meta, carpeta, reproducir_audio, max_seg,
                                       retener, fs):
        esquema, spb = meta["esquema"], meta["spb"]
        self._progreso("demodulacion", f"Demodulando ({esquema})...", 70)
        bits_rec, est, umbral = demodular(x, esquema, fs, spb)
        self._progreso("demodulacion", f"{len(bits_rec):,} bits recuperados", 72)
        capas_bytes, h = parsear_trama_capas(bits_rec)
        img = reconstruir_desde_capas(capas_bytes, h["ancho"], h["alto"])
        crc_txt = "OK" if h["crc_ok"] else "FALLO"
        self._progreso(
            "demodulacion",
            f"Cabecera v{h['version']}: {h['ancho']}x{h['alto']} px, "
            f"{h['n_capas']} capas WebP, CRC32 {crc_txt}",
            74,
        )
        return bits_rec, est, umbral, img, capas_bytes, h
