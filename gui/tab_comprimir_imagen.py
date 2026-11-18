"""Pestaña de compresión de imagen WebP lossless → PNG (Desafío 4, punto 2).

Carga la imagen del Desafío 3 (BMP, PNG, JPG, JPEG o WebP), la comprime a
WebP sin pérdida, la descomprime a PNG y muestra métricas de reconstrucción
(MAE, RMSE, PSNR y porcentaje de píxeles idénticos).
"""
from __future__ import annotations

import datetime as _dt
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image as PILImage, ImageDraw
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from core.compression_image import (
    ImageCompressionError, ImageCompressionResult, compare_images,
    compress_image, decompress_image, image_array, load_image,
)
from gui.widgets import ImageViewer, StatusLabel

IMAGE_FILTERS = (
    "Imágenes (*.png *.bmp *.jpg *.jpeg *.webp *.svg);;"
    "PNG (*.png);;BMP (*.bmp);;JPEG (*.jpg *.jpeg);;WebP (*.webp);;SVG (*.svg);;"
    "Todos los archivos (*.*)"
)


def output_dir() -> Path:
    """Carpeta de salidas de la compresión de imagen."""
    folder = Path(__file__).resolve().parents[1] / "salida_desafio4" / "compresion_imagen"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


class TabComprimirImagen(QWidget):
    """Pestaña PyQt6 para comprimir y verificar imágenes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._src: Path | None = None
        self._webp: Path | None = None
        self._png: Path | None = None
        self._result: ImageCompressionResult | None = None
        self._setup_ui()

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # ---- Controles ----
        grp = QGroupBox("Compresión sin pérdida de imagen (WebP → PNG)")
        controls = QVBoxLayout()
        controls.setSpacing(8)

        fila1 = QHBoxLayout()
        self.btn_elegir = QPushButton("📂 Elegir imagen")
        self.btn_elegir.setMinimumHeight(36)
        self.btn_elegir.clicked.connect(self._elegir_imagen)
        self.lbl_archivo = QLabel("Ninguna imagen cargada")
        self.lbl_archivo.setWordWrap(True)
        self.lbl_archivo.setStyleSheet("color: #666; font-size: 12px;")
        fila1.addWidget(self.btn_elegir)
        fila1.addWidget(self.lbl_archivo, stretch=1)
        controls.addLayout(fila1)

        fila2 = QHBoxLayout()
        self.chk_lossless = QCheckBox("Compresión sin pérdida (lossless)")
        self.chk_lossless.setChecked(True)
        self.chk_lossless.toggled.connect(lambda _checked: self._on_lossless_changed())
        fila2.addWidget(self.chk_lossless)

        fila2.addWidget(QLabel("Calidad:"))
        self.spin_calidad = QSpinBox()
        self.spin_calidad.setRange(1, 100)
        self.spin_calidad.setValue(90)
        self.spin_calidad.setSuffix(" %")
        self.spin_calidad.setEnabled(False)
        fila2.addWidget(self.spin_calidad)

        fila2.addWidget(QLabel("Modo al reconstruir:"))
        self.combo_modo = QComboBox()
        self.combo_modo.addItems(["RGB", "RGBA"])
        fila2.addWidget(self.combo_modo)

        fila2.addWidget(QLabel("Vista:"))
        self.combo_vista = QComboBox()
        self.combo_vista.addItems(["Comparar", "Original", "Reconstruida", "Diferencia"])
        self.combo_vista.currentTextChanged.connect(lambda _texto: self._refresh())
        fila2.addWidget(self.combo_vista)
        fila2.addStretch()
        controls.addLayout(fila2)

        fila3 = QHBoxLayout()
        self.btn_comprimir = QPushButton("🗜 Comprimir a WebP")
        self.btn_comprimir.clicked.connect(self._comprimir)
        self.btn_descomprimir = QPushButton("📂 Descomprimir WebP")
        self.btn_descomprimir.clicked.connect(self._descomprimir)
        self.btn_verificar = QPushButton("✅ Verificar")
        self.btn_verificar.clicked.connect(self._verificar)
        self.btn_abrir = QPushButton("🔎 Abrir salidas")
        self.btn_abrir.clicked.connect(self._abrir_salidas)
        for b in (self.btn_comprimir, self.btn_descomprimir, self.btn_verificar, self.btn_abrir):
            b.setMinimumHeight(34)
            fila3.addWidget(b)
        controls.addLayout(fila3)

        self.lbl_info = QLabel(
            "Elija una imagen BMP/PNG/JPG/JPEG/WebP y pulse «Comprimir a WebP»."
        )
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet(
            "color: #444; font-size: 12px; background: #fff; border: 1px solid #ddd; "
            "border-radius: 4px; padding: 6px;"
        )
        controls.addWidget(self.lbl_info)

        self.lbl_aviso = QLabel(
            "WebP en modo lossless conserva todos los píxeles. Si la imagen de origen es "
            "JPG/JPEG, el WebP lossless puede salir MÁS grande: el JPG ya descartó "
            "información y el WebP sin pérdida debe guardar todos los píxeles. Use un "
            "PNG/BMP como origen o active la compresión con pérdida si necesita reducir "
            "el tamaño. Los SVG son vectoriales: conviértalos a PNG antes de comprimir."
        )
        self.lbl_aviso.setWordWrap(True)
        self.lbl_aviso.setStyleSheet("color: #888; font-size: 11px;")
        controls.addWidget(self.lbl_aviso)
        grp.setLayout(controls)
        layout.addWidget(grp)

        # ---- Visores ----
        vistas = QHBoxLayout()
        vistas.setSpacing(8)
        self.panel_original = self._crear_panel("Original", "Sin imagen cargada")
        self.panel_reconstruida = self._crear_panel("Reconstruida (PNG)", "Sin reconstrucción")
        self.panel_diferencia = self._crear_panel(
            "Diferencia ×8 (negro = idéntica)", "Sin comparación"
        )
        for panel in (self.panel_original, self.panel_reconstruida, self.panel_diferencia):
            vistas.addWidget(panel, stretch=1)
        layout.addLayout(vistas, stretch=1)

        self.lbl_estado = StatusLabel("Listo")
        layout.addWidget(self.lbl_estado)
        self._actualizar_botones()

    def _crear_panel(self, titulo: str, placeholder: str) -> QGroupBox:
        grp = QGroupBox(titulo)
        lay = QVBoxLayout()
        lay.setContentsMargins(4, 4, 4, 4)
        viewer = ImageViewer(placeholder_text=placeholder)
        lay.addWidget(viewer)
        grp.setLayout(lay)
        grp.viewer = viewer  # type: ignore[attr-defined]
        return grp

    # ------------------------------------------------------------------ #
    # Acciones
    # ------------------------------------------------------------------ #
    def _on_lossless_changed(self) -> None:
        self.spin_calidad.setEnabled(not self.chk_lossless.isChecked())

    def _elegir_imagen(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Abrir imagen del Desafío 3", str(output_dir()), IMAGE_FILTERS
        )
        if not ruta:
            return
        self._src = Path(ruta)
        self._webp = None
        self._png = None
        self._result = None
        self.lbl_archivo.setText(f"Imagen de origen: {self._src.name}")
        self.lbl_info.setText(f"Imagen cargada: {self._src.name}")
        self.lbl_estado.set_ok("Imagen lista para comprimir.")
        self._actualizar_botones()
        self._refresh()

    def _comprimir(self) -> None:
        if self._src is None:
            QMessageBox.information(self, "Comprimir", "Elija primero una imagen.")
            return
        desp, _ = QFileDialog.getSaveFileName(
            self, "Guardar imagen comprimida (WebP)",
            str(output_dir() / f"imagen_comprimida_{_timestamp()}.webp"),
            "WebP (*.webp)",
        )
        if not desp:
            return
        try:
            resultado = compress_image(
                self._src,
                desp,
                lossless=self.chk_lossless.isChecked(),
                quality=self.spin_calidad.value(),
            )
        except ImageCompressionError as exc:
            QMessageBox.critical(self, "Comprimir imagen", str(exc))
            self.lbl_estado.set_error("No se pudo comprimir la imagen.")
            return

        self._webp = Path(desp)
        self._png = None
        self._result = resultado
        idx = self.combo_modo.findText(resultado.mode)
        if idx >= 0:
            self.combo_modo.setCurrentIndex(idx)
        self.lbl_info.setText(resultado.summary())
        self.lbl_estado.set_ok(
            f"Imagen comprimida: {self._src.name} → {self._webp.name} "
            f"({resultado.original_size:,} → {resultado.compressed_size:,} bytes, "
            f"{resultado.ratio:.2f}×)."
        )
        self._actualizar_botones()
        self._refresh()

    def _descomprimir(self) -> None:
        webp = self._webp
        if webp is None or not webp.is_file():
            ruta, _ = QFileDialog.getOpenFileName(
                self, "Abrir WebP a descomprimir", str(output_dir()), "WebP (*.webp)"
            )
            if not ruta:
                return
            webp = Path(ruta)

        desp, _ = QFileDialog.getSaveFileName(
            self, "Guardar imagen reconstruida (PNG)",
            str(output_dir() / f"imagen_reconstruida_{_timestamp()}.png"),
            "PNG (*.png)",
        )
        if not desp:
            return

        esperado = ""
        if self._result is not None and self._webp == webp:
            esperado = self._result.pixel_sha256
        try:
            resultado = decompress_image(
                webp, desp, mode=self.combo_modo.currentText(), expected_sha256=esperado
            )
        except ImageCompressionError as exc:
            QMessageBox.critical(self, "Descomprimir imagen", str(exc))
            self.lbl_estado.set_error("No se pudo descomprimir el WebP.")
            return

        self._webp = webp
        self._png = Path(desp)
        if self._result is not None:
            anterior = self._result
            resultado.original_size = anterior.original_size
            resultado.compressed = anterior.compressed
            resultado.lossless = anterior.lossless
            resultado.quality = anterior.quality
            resultado.original_format = anterior.original_format
        self._result = resultado
        self.lbl_info.setText(resultado.summary())
        self.lbl_estado.set_ok(f"Imagen reconstruida en {self._png.name}.")
        self._actualizar_botones()
        self._refresh()

    def _verificar(self) -> None:
        original, _ = QFileDialog.getOpenFileName(
            self, "Imagen original para verificar",
            str(self._src.parent) if self._src else str(output_dir()), IMAGE_FILTERS,
        )
        if not original:
            return
        restaurada, _ = QFileDialog.getOpenFileName(
            self, "Imagen reconstruida para verificar",
            str(self._png.parent) if self._png else str(output_dir()), "PNG (*.png)",
        )
        if not restaurada:
            return
        try:
            resultado = compare_images(original, restaurada)
        except ImageCompressionError as exc:
            QMessageBox.critical(self, "Verificar imagen", str(exc))
            self.lbl_estado.set_error("No se pudo verificar.")
            return

        if self._result is not None:
            anterior = self._result
            resultado.original_size = anterior.original_size
            resultado.compressed = anterior.compressed
            resultado.compressed_size = anterior.compressed_size
            resultado.lossless = anterior.lossless
            resultado.quality = anterior.quality
            resultado.original_format = anterior.original_format
        self._result = resultado
        self._src = Path(original)
        self._png = Path(restaurada)
        self.lbl_info.setText(
            f"Verificación: {resultado.identical_percent:.4f} % de píxeles idénticos "
            f"({'píxeles idénticos (bit a bit).' if resultado.exact else 'hay diferencias.'})\n"
            + resultado.summary()
        )
        if resultado.exact:
            self.lbl_estado.set_ok("Verificación: píxeles EXACTOS (bit a bit).")
        else:
            self.lbl_estado.set_warning("Verificación: hay diferencias entre las imágenes.")
        self._actualizar_botones()
        self._refresh()

    def _actualizar_botones(self) -> None:
        self.btn_descomprimir.setEnabled(
            self._webp is not None and self._webp.is_file()
        )
        self.btn_verificar.setEnabled(
            self._src is not None and self._src.is_file()
            and self._png is not None and self._png.is_file()
        )

    def _abrir_salidas(self) -> None:
        folder = output_dir()
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform.startswith("darwin"):
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
            self.lbl_estado.set_text(f"Carpeta abierta: {folder}")
        except Exception as exc:
            QMessageBox.critical(self, "Abrir salidas", f"No se pudo abrir {folder}: {exc}")

    # ------------------------------------------------------------------ #
    # Visualización
    # ------------------------------------------------------------------ #
    @staticmethod
    def _para_mostrar(arr: np.ndarray | None) -> np.ndarray | None:
        """ Convierte a RGB para el visor (compone transparencia sobre blanco). """
        if arr is None:
            return None
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
        if arr.shape[2] == 4:
            rgb = arr[..., :3].astype(np.float32)
            alpha = arr[..., 3:4].astype(np.float32) / 255.0
            rgb = rgb * alpha + 255.0 * (1.0 - alpha)
            return np.clip(rgb, 0, 255).astype(np.uint8)
        return np.ascontiguousarray(arr[..., :3], dtype=np.uint8)

    @classmethod
    def _diferencia(
        cls, original: np.ndarray, restaurada: np.ndarray
    ) -> tuple[np.ndarray, bool, bool]:
        """Dibuja |original - restaurada| ×8 con fondo opaco negro.

        Se comparan solo los canales RGB: si se usara el array RGBA completo,
        el canal alfa de la diferencia valdría 0 y la imagen se vería blanca
        en vez del negro que indica «idéntica».
        """
        rgb = np.abs(
            original[..., :3].astype(np.int16) - restaurada[..., :3].astype(np.int16)
        )
        amplificada = np.clip(rgb * 8, 0, 255).astype(np.uint8)
        alpha_distinto = original.shape[2] == 4 and not np.array_equal(
            original[..., 3], restaurada[..., 3]
        )
        identica = int(rgb.max()) == 0 and not alpha_distinto
        return amplificada, identica, alpha_distinto

    @staticmethod
    def _con_texto(arr: np.ndarray, texto: str) -> np.ndarray:
        """Superpone texto centrado sobre la imagen (para el aviso de igualdad)."""
        img = PILImage.fromarray(arr).convert("RGB")
        draw = ImageDraw.Draw(img)
        w, h = img.size
        lineas = texto.split("\n")
        alto_linea = 12
        y = h / 2 - (len(lineas) * alto_linea) / 2
        for linea in lineas:
            ancho = 6 * len(linea)  # ancho aproximado con la fuente por defecto
            draw.text((int(w / 2 - ancho / 2), int(y)), linea, fill="white")
            y += alto_linea
        return np.asarray(img)

    def _refresh(self) -> None:
        vista = self.combo_vista.currentText()
        original = restaurada = None
        if self._src is not None and self._src.is_file():
            try:
                original = image_array(load_image(self._src)[0])
            except ImageCompressionError as exc:
                self.lbl_estado.set_error(str(exc))
        if self._png is not None and self._png.is_file():
            try:
                restaurada = image_array(load_image(self._png)[0])
            except ImageCompressionError:
                restaurada = None

        paneles = {
            "original": self.panel_original,
            "reconstruida": self.panel_reconstruida,
            "diferencia": self.panel_diferencia,
        }
        for panel in paneles.values():
            panel.hide()

        if original is None and restaurada is None:
            self.lbl_info.setText(
                "Elija una imagen para comprimir.\n"
                "Descomprima el WebP para ver la reconstrucción."
            )
            return

        dif_listo = original is not None and restaurada is not None \
            and original.shape == restaurada.shape
        diff_arr = identica = alpha_distinto = None
        if dif_listo:
            diff_arr, identica, alpha_distinto = self._diferencia(original, restaurada)

        if vista == "Comparar":
            seleccionadas = ["original", "reconstruida", "diferencia"] if dif_listo \
                else ["original", "reconstruida"]
        elif vista == "Original":
            seleccionadas = ["original"]
        elif vista == "Reconstruida":
            seleccionadas = ["reconstruida"]
        else:
            seleccionadas = ["diferencia"] if dif_listo else []

        for clave in seleccionadas:
            panel = paneles[clave]
            panel.show()
            if clave == "original" and original is not None:
                panel.viewer.set_image(self._para_mostrar(original))
                panel.setTitle(f"Original · {self._src.name if self._src else ''}")
            elif clave == "reconstruida" and restaurada is not None:
                panel.viewer.set_image(self._para_mostrar(restaurada))
                panel.setTitle("Reconstruida (PNG)")
            elif clave == "diferencia" and diff_arr is not None:
                display = diff_arr
                if identica:
                    display = self._con_texto(
                        diff_arr, "Sin diferencias\n(imágenes idénticas)"
                    )
                panel.viewer.set_image(display)
                titulo = (
                    "Diferencia ×8 (negro = idéntica)" if vista == "Comparar"
                    else "Diferencia ×8"
                )
                if alpha_distinto:
                    titulo += " · ALFA DISTINTO"
                panel.setTitle(titulo)

        self.lbl_info.setText(self._result.summary() if self._result else self.lbl_info.text())
