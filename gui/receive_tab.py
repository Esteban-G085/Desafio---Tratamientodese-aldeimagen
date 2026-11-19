"""
Pestaña 'Recibir': el compañero carga el ZIP, demodula y recupera la imagen.
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QVBoxLayout, QWidget, QSizePolicy,
)

from gui.widgets import ImageViewer, StatusLabel
from gui.worker import PipelineWorker


class ReceiveTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.resultado = None
        self.ruta_zip = None
        self._setup_ui()

    # ------------------------------------------------------------------ #
    #  UI
    # ------------------------------------------------------------------ #
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 16)

        # ============ FILA 1: selección ZIP ============
        grp_zip = QGroupBox("1. Paquete recibido (ZIP)")
        v = QVBoxLayout()
        v.setSpacing(10)

        self.btn_seleccionar = QPushButton("Seleccionar paquete_para_companero.zip")
        self.btn_seleccionar.setMinimumHeight(42)
        self.btn_seleccionar.clicked.connect(self._seleccionar_zip)
        v.addWidget(self.btn_seleccionar)

        self.lbl_zip = QLabel("Ningún paquete seleccionado")
        self.lbl_zip.setWordWrap(True)
        self.lbl_zip.setStyleSheet("color: #666; font-size: 12px;")
        v.addWidget(self.lbl_zip)

        grp_zip.setLayout(v)
        layout.addWidget(grp_zip)

        # ============ FILA 1b: tipo de paquete ============
        grp_tipo = QGroupBox("Tipo de paquete recibido")
        vt = QHBoxLayout()
        self.combo_flujo = QComboBox()
        self.combo_flujo.addItems([
            "Detección automática",
            "WAV modulado (capas WebP)",
            "WebP directo (sin modulación)",
        ])
        vt.addWidget(self.combo_flujo)
        grp_tipo.setLayout(vt)
        layout.addWidget(grp_tipo)

        # ============ FILA 2: imagen recuperada (con scroll) ============
        self.lbl_tit_img = QLabel("2. Imagen recuperada")
        self.lbl_tit_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_tit_img.setStyleSheet("font-weight: bold; font-size: 13px; color: #333;")
        layout.addWidget(self.lbl_tit_img)

        self.img_recuperada = ImageViewer(placeholder_text="Sin imagen procesada")
        self.img_recuperada.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.img_recuperada, stretch=1)

        # ============ FILA 3: información del paquete ============
        self.lbl_info = QLabel("")
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_info.setStyleSheet("font-size: 12px; color: #555; padding: 6px;")
        layout.addWidget(self.lbl_info)

        # ============ FILA 4: progreso ============
        self.progreso = QProgressBar()
        self.progreso.setRange(0, 100)
        self.progreso.setValue(0)
        self.progreso.setTextVisible(True)
        self.progreso.setMinimumHeight(22)
        layout.addWidget(self.progreso)

        self.lbl_estado = StatusLabel("Listo")
        layout.addWidget(self.lbl_estado)

        # ============ FILA 5: botón procesar ============
        self.btn_procesar = QPushButton("Procesar recepción")
        self.btn_procesar.setMinimumHeight(50)
        self.btn_procesar.setStyleSheet(
            "QPushButton { background-color: #388e3c; color: white; "
            "font-weight: bold; font-size: 14px; border-radius: 6px; padding: 12px 24px; }"
            "QPushButton:disabled { background-color: #a5d6a7; color: #ffffff; }"
        )
        self.btn_procesar.clicked.connect(self._iniciar_recepcion)
        self.btn_procesar.setEnabled(False)
        layout.addWidget(self.btn_procesar)

        # ============ FILA 6: acciones ============
        h_btn = QHBoxLayout()
        h_btn.setSpacing(10)

        self.btn_abrir_carpeta = QPushButton("Abrir carpeta de salida")
        self.btn_abrir_carpeta.setMinimumHeight(40)
        self.btn_abrir_carpeta.clicked.connect(self._abrir_carpeta)
        self.btn_abrir_carpeta.setEnabled(False)
        h_btn.addWidget(self.btn_abrir_carpeta)

        self.btn_audio = QPushButton("Reproducir audio demodulado")
        self.btn_audio.setMinimumHeight(40)
        self.btn_audio.clicked.connect(self._reproducir_audio)
        self.btn_audio.setEnabled(False)
        h_btn.addWidget(self.btn_audio)

        h_btn.addStretch()
        layout.addLayout(h_btn)

        layout.addStretch()

    # ------------------------------------------------------------------ #
    #  Acciones
    # ------------------------------------------------------------------ #
    def _seleccionar_zip(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar ZIP", "", "Archivos ZIP (*.zip)"
        )
        if not ruta:
            return

        self.ruta_zip = ruta
        self.lbl_zip.setText(os.path.basename(ruta))
        self.lbl_zip.setStyleSheet("color: #000000; font-weight: bold; font-size: 12px;")
        self.btn_procesar.setEnabled(True)
        self.btn_audio.setEnabled(False)
        self.btn_abrir_carpeta.setEnabled(False)
        self.img_recuperada.clear()
        self.lbl_info.setText("")
        self.lbl_estado.set_ok("ZIP seleccionado. Listo para procesar.")

    def _iniciar_recepcion(self):
        if self.worker is not None and self.worker.isRunning():
            return

        flujos = {0: "auto", 1: "wav", 2: "directo"}
        kwargs = {
            "paquete_zip": self.ruta_zip,
            "salida": "recibido",
            "reproducir_audio": False,
            "mostrar_graficas": True,
            "escuchar_seg": 8,
            "retener": 10,
            "flujo": flujos[self.combo_flujo.currentIndex()],
        }

        self.btn_seleccionar.setEnabled(False)
        self.btn_procesar.setEnabled(False)
        self.combo_flujo.setEnabled(False)
        self.progreso.setValue(0)
        self.lbl_estado.set_text("Procesando recepción...")
        self.worker = PipelineWorker(mode="receive", **kwargs)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, stage, message, percent):
        self.progreso.setValue(int(percent))
        self.lbl_estado.set_text(message)

    def _on_finished(self, resultado):
        self.resultado = resultado

        self.btn_seleccionar.setEnabled(True)
        self.btn_procesar.setEnabled(True)
        self.combo_flujo.setEnabled(True)
        self.btn_abrir_carpeta.setEnabled(True)
        self.btn_audio.setEnabled(bool(resultado.get("ruta_audio")))

        self.img_recuperada.set_image(resultado["imagen_recuperada"], max_display=700)

        meta = resultado["meta"]
        h = resultado.get("header", {})
        flujo = resultado.get("flujo", "wav")
        if flujo == "directo":
            self.lbl_info.setText(
                f"WebP directo | calidad {meta.get('calidad', '?')}% | "
                f"{h.get('ancho', '?')}x{h.get('alto', '?')} px | "
                f"{h.get('n_capas', 3)} capas R/G/B | "
                f"{resultado.get('tam_webp_kb', 0):.1f} KB"
            )
            detalle = (
                f"Flujo: WebP directo (sin modulación)\n"
                f"Capas descomprimidas: {h.get('n_capas', 3)}\n"
                f"Tamaño WebP: {resultado.get('tam_webp_kb', 0):.1f} KB"
            )
        else:
            self.lbl_info.setText(
                f"{meta['esquema']} a {meta['baud']:.0f} bps, fs = {meta['fs']} Hz | "
                f"{h.get('ancho', '?')}x{h.get('alto', '?')} px, "
                f"{h.get('bits', '?')} bits/canal, CRC32: {'OK' if h.get('crc_ok') else 'FALLO'}"
            )
            detalle = f"Esquema: {meta['esquema']}\nCRC32: {'OK' if h.get('crc_ok') else 'FALLO'}"

        self.lbl_estado.set_ok("Recepción completada exitosamente")

        QMessageBox.information(
            self, "Recepción completada",
            f"Imagen recuperada guardada en:\n{resultado['ruta_png']}\n\n{detalle}"
        )

    def _on_error(self, mensaje):
        self.btn_seleccionar.setEnabled(True)
        self.btn_procesar.setEnabled(True)
        self.combo_flujo.setEnabled(True)
        self.lbl_estado.set_error(mensaje)
        QMessageBox.critical(self, "Error de recepción", mensaje)

    def _abrir_carpeta(self):
        if not self.resultado:
            return
        ruta = self.resultado["salida"]
        if hasattr(os, "startfile"):
            os.startfile(ruta)

    def _reproducir_audio(self):
        if not self.resultado:
            return
        try:
            if hasattr(os, "startfile"):
                os.startfile(self.resultado["ruta_audio"])
        except Exception as e:
            QMessageBox.information(
                self, "Audio",
                f"No se pudo reproducir:\n{self.resultado['ruta_audio']}\n\n{e}"
            )
