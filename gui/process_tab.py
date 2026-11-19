"""
Pestaña 'Procesar': el usuario carga una foto, elige parámetros y lanza el pipeline.
"""

import os

import cv2

from PyQt6.QtCore import Qt, QThread
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QGroupBox,
    QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
    QSpinBox, QVBoxLayout, QWidget, QGridLayout, QSizePolicy,
)

from gui.widgets import ImageViewer, StatusLabel, PresetButton
from gui.worker import PipelineWorker


class ProcessTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.resultado = None
        self.ruta_foto = None
        self._setup_ui()

    # ------------------------------------------------------------------ #
    #  UI
    # ------------------------------------------------------------------ #
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ============ FILA 1: archivo + previsualizaciones ============
        fila1 = QHBoxLayout()
        fila1.setSpacing(10)

        # Panel izquierdo: selección de archivo (ancho fijo)
        panel_archivo = QWidget()
        panel_archivo.setMinimumWidth(220)
        panel_archivo.setMaximumWidth(300)
        pv = QVBoxLayout(panel_archivo)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(10)

        grp_archivo = QGroupBox("1. Foto de entrada")
        va = QVBoxLayout()
        self.btn_seleccionar = QPushButton("Seleccionar foto (JPG/JPEG/PNG)")
        self.btn_seleccionar.setMinimumHeight(42)
        self.btn_seleccionar.clicked.connect(self._seleccionar_foto)
        self.lbl_archivo = QLabel("Ningún archivo seleccionado")
        self.lbl_archivo.setWordWrap(True)
        self.lbl_archivo.setStyleSheet("color: #666; font-size: 12px;")
        va.addWidget(self.btn_seleccionar)
        va.addWidget(self.lbl_archivo)
        va.addStretch()
        grp_archivo.setLayout(va)
        pv.addWidget(grp_archivo)
        pv.addStretch()
        fila1.addWidget(panel_archivo)

        # Panel central: imagen original (con scroll)
        self.panel_original = self._crear_panel_imagen("Original", "Sin imagen cargada")
        fila1.addWidget(self.panel_original, stretch=1)

        # Panel derecho: imagen filtrada (con scroll)
        self.panel_filtrada = self._crear_panel_imagen("Filtro rojo dominante", "Se muestra tras procesar")
        fila1.addWidget(self.panel_filtrada, stretch=1)

        layout.addLayout(fila1, stretch=2)

        # ============ FILA 2: configuraciones base (presets) ============
        grp_presets = QGroupBox("Configuraciones base (presets)")
        pv2 = QVBoxLayout()
        pv2.setSpacing(10)

        h_presets = QHBoxLayout()
        h_presets.setSpacing(10)

        self.btn_preset_rapido = PresetButton(
            "Rápido",
            "Ancho 32 px, 4 bits, FSK",
            {"mod": "FSK", "bits": 4, "ancho": 32, "fs": 44100, "baud": 4410, "snr": None},
        )
        self.btn_preset_calidad = PresetButton(
            "Calidad",
            "Ancho 128 px, 8 bits, PSK",
            {"mod": "PSK", "bits": 8, "ancho": 128, "fs": 44100, "baud": 4410, "snr": None},
        )
        self.btn_preset_ruidoso = PresetButton(
            "Con ruido",
            "Ancho 64 px, 6 bits, ASK, SNR 10 dB",
            {"mod": "ASK", "bits": 6, "ancho": 64, "fs": 44100, "baud": 4410, "snr": 10},
        )
        self.btn_preset_personalizado = PresetButton(
            "Personalizado",
            "Usa tus propios valores",
            {},
        )

        for btn in (self.btn_preset_rapido, self.btn_preset_calidad,
                    self.btn_preset_ruidoso, self.btn_preset_personalizado):
            h_presets.addWidget(btn)

        h_presets.addStretch()
        pv2.addLayout(h_presets)

        self.btn_preset_rapido.clicked.connect(
            lambda: self._aplicar_preset(self.btn_preset_rapido.valores)
        )
        self.btn_preset_calidad.clicked.connect(
            lambda: self._aplicar_preset(self.btn_preset_calidad.valores)
        )
        self.btn_preset_ruidoso.clicked.connect(
            lambda: self._aplicar_preset(self.btn_preset_ruidoso.valores)
        )
        self.btn_preset_personalizado.clicked.connect(self._limpiar_preset)

        grp_presets.setLayout(pv2)
        layout.addWidget(grp_presets)

        # ============ FILA 3: parámetros de transmisión ============
        grp_param = QGroupBox("2. Parámetros de transmisión")
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(12)

        grid.addWidget(self._label_param("Modulación:"), 0, 0, Qt.AlignmentFlag.AlignRight)
        self.combo_mod = QComboBox()
        self.combo_mod.addItems(["ASK", "FSK", "PSK"])
        self.combo_mod.setCurrentIndex(1)
        self.combo_mod.setMinimumWidth(150)
        grid.addWidget(self.combo_mod, 0, 1)

        grid.addWidget(self._label_param("Bits por muestra:"), 1, 0, Qt.AlignmentFlag.AlignRight)
        self.spin_bits = QSpinBox()
        self.spin_bits.setRange(1, 8)
        self.spin_bits.setValue(8)
        self.spin_bits.setMinimumWidth(150)
        grid.addWidget(self.spin_bits, 1, 1)

        grid.addWidget(self._label_param("Ancho de trabajo (px):"), 2, 0, Qt.AlignmentFlag.AlignRight)
        self.spin_ancho = QSpinBox()
        self.spin_ancho.setRange(16, 512)
        self.spin_ancho.setValue(64)
        self.spin_ancho.setMinimumWidth(150)
        grid.addWidget(self.spin_ancho, 2, 1)

        grid.addWidget(self._label_param("fs audio (Hz):"), 0, 2, Qt.AlignmentFlag.AlignRight)
        self.spin_fs = QSpinBox()
        self.spin_fs.setRange(8000, 96000)
        self.spin_fs.setValue(44100)
        self.spin_fs.setSingleStep(1000)
        self.spin_fs.setMinimumWidth(150)
        grid.addWidget(self.spin_fs, 0, 3)

        grid.addWidget(self._label_param("Baud (bps):"), 1, 2, Qt.AlignmentFlag.AlignRight)
        self.spin_baud = QDoubleSpinBox()
        self.spin_baud.setRange(100, 20000)
        self.spin_baud.setValue(4410)
        self.spin_baud.setMinimumWidth(150)
        grid.addWidget(self.spin_baud, 1, 3)

        grid.addWidget(self._label_param("SNR (dB):"), 2, 2, Qt.AlignmentFlag.AlignRight)
        self.spin_snr = QDoubleSpinBox()
        self.spin_snr.setRange(0, 60)
        self.spin_snr.setValue(0)
        self.spin_snr.setSpecialValueText("Sin ruido")
        self.spin_snr.setMinimumWidth(150)
        grid.addWidget(self.spin_snr, 2, 3)

        grid.addWidget(self._label_param("Entrega al compañero:"), 3, 0, Qt.AlignmentFlag.AlignRight)
        self.combo_flujo = QComboBox()
        self.combo_flujo.addItems([
            "Ambos (WAV + WebP)",
            "Solo WAV modulado",
            "Solo WebP directo",
        ])
        self.combo_flujo.setMinimumWidth(150)
        grid.addWidget(self.combo_flujo, 3, 1)

        grid.addWidget(self._label_param("Calidad WebP (%):"), 3, 2, Qt.AlignmentFlag.AlignRight)
        self.spin_calidad = QSpinBox()
        self.spin_calidad.setRange(1, 100)
        self.spin_calidad.setValue(85)
        self.spin_calidad.setMinimumWidth(150)
        grid.addWidget(self.spin_calidad, 3, 3)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grp_param.setLayout(grid)
        layout.addWidget(grp_param)

        # Opciones
        row_opts = QHBoxLayout()
        self.chk_audio = QCheckBox("Reproducir audio durante el proceso")
        self.chk_graficas = QCheckBox("Generar y guardar gráficas (PNG)")
        self.chk_graficas.setChecked(True)
        row_opts.addWidget(self.chk_audio)
        row_opts.addWidget(self.chk_graficas)
        row_opts.addStretch()
        layout.addLayout(row_opts)

        # ============ FILA 4: botón ejecutar + progreso ============
        self.btn_procesar = QPushButton("Procesar imagen")
        self.btn_procesar.setMinimumHeight(50)
        self.btn_procesar.setStyleSheet(
            "QPushButton { background-color: #1976d2; color: white; "
            "font-weight: bold; font-size: 14px; border-radius: 6px; padding: 12px 24px; }"
            "QPushButton:disabled { background-color: #90caf9; color: #ffffff; }"
        )
        self.btn_procesar.clicked.connect(self._iniciar_procesamiento)
        self.btn_procesar.setEnabled(False)
        layout.addWidget(self.btn_procesar)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 100)
        self.progreso.setValue(0)
        self.progreso.setTextVisible(True)
        self.progreso.setMinimumHeight(22)
        layout.addWidget(self.progreso)

        self.lbl_estado = StatusLabel("Listo")
        layout.addWidget(self.lbl_estado)

        # ============ FILA 5: resultados (imagen + métricas) ============
        fila5 = QHBoxLayout()
        fila5.setSpacing(10)

        # Panel: imagen reconstruida (con scroll)
        self.panel_reconstruida = self._crear_panel_imagen("3. Imagen reconstruida", "Sin resultados")
        fila5.addWidget(self.panel_reconstruida, stretch=2)

        # Panel: métricas y acciones (ancho fijo razonable)
        panel_acc = QWidget()
        panel_acc.setMinimumWidth(340)
        panel_acc.setMaximumWidth(420)
        pa = QVBoxLayout(panel_acc)
        pa.setContentsMargins(0, 0, 0, 0)
        pa.setSpacing(12)

        grp_metricas = QGroupBox("Métricas")
        vm = QVBoxLayout()
        self.lbl_metricas = QLabel("MSE: —   PSNR: —   BER: —   Errores: —")
        self.lbl_metricas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_metricas.setStyleSheet(
            "font-family: 'Consolas', 'Monospace'; font-size: 12px; padding: 12px;"
        )
        vm.addWidget(self.lbl_metricas)
        grp_metricas.setLayout(vm)
        pa.addWidget(grp_metricas)

        grp_acciones = QGroupBox("Acciones")
        va2 = QVBoxLayout()
        self.btn_abrir_carpeta = QPushButton("Abrir carpeta de salida")
        self.btn_abrir_carpeta.setMinimumHeight(40)
        self.btn_abrir_carpeta.clicked.connect(self._abrir_carpeta)
        self.btn_abrir_carpeta.setEnabled(False)

        self.btn_audio_mod = QPushButton("Reproducir WAV modulado")
        self.btn_audio_mod.setMinimumHeight(40)
        self.btn_audio_mod.clicked.connect(self._reproducir_audio_modulado)
        self.btn_audio_mod.setEnabled(False)

        self.btn_audio_demo = QPushButton("Reproducir WAV demodulado")
        self.btn_audio_demo.setMinimumHeight(40)
        self.btn_audio_demo.clicked.connect(self._reproducir_audio_demodulado)
        self.btn_audio_demo.setEnabled(False)

        va2.addWidget(self.btn_abrir_carpeta)
        va2.addWidget(self.btn_audio_mod)
        va2.addWidget(self.btn_audio_demo)
        va2.addStretch()
        grp_acciones.setLayout(va2)
        pa.addWidget(grp_acciones)
        pa.addStretch()

        fila5.addWidget(panel_acc)
        layout.addLayout(fila5, stretch=2)

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    def _crear_panel_imagen(self, titulo, placeholder):
        """Crea un panel con título y visor de imagen con scroll."""
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(6)

        lbl = QLabel(titulo)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #333;")
        panel_layout.addWidget(lbl)

        viewer = ImageViewer(placeholder_text=placeholder)
        viewer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        panel_layout.addWidget(viewer, stretch=1)

        panel.viewer = viewer
        return panel

    @staticmethod
    def _label_param(texto):
        lbl = QLabel(texto)
        lbl.setStyleSheet("font-size: 12px; color: #333;")
        return lbl

    def _aplicar_preset(self, valores):
        if not valores:
            return
        if "mod" in valores:
            idx = self.combo_mod.findText(valores["mod"])
            if idx >= 0:
                self.combo_mod.setCurrentIndex(idx)
        if "bits" in valores:
            self.spin_bits.setValue(valores["bits"])
        if "ancho" in valores:
            self.spin_ancho.setValue(valores["ancho"])
        if "fs" in valores:
            self.spin_fs.setValue(valores["fs"])
        if "baud" in valores:
            self.spin_baud.setValue(float(valores["baud"]))
        if "snr" in valores:
            if valores["snr"] is None:
                self.spin_snr.setValue(0)
            else:
                self.spin_snr.setValue(float(valores["snr"]))
        self.lbl_estado.set_ok("Preset aplicado")

    def _limpiar_preset(self):
        self.lbl_estado.set_text("Valores personalizados activos.")

    # ------------------------------------------------------------------ #
    #  Acciones
    # ------------------------------------------------------------------ #
    def _seleccionar_foto(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar foto", "",
            "Imágenes (*.jpg *.jpeg *.png *.bmp *.tif *.tiff)"
        )
        if not ruta:
            return

        self.ruta_foto = ruta
        self.lbl_archivo.setText(os.path.basename(ruta))
        self.lbl_archivo.setStyleSheet("color: #000000; font-weight: bold; font-size: 12px;")
        self.btn_procesar.setEnabled(True)

        img = cv2.imread(ruta)
        if img is not None:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            self.panel_original.viewer.set_image(img, max_display=700)
            self.panel_filtrada.viewer.clear()
            self.panel_reconstruida.viewer.clear()
            self.lbl_estado.set_ok("Imagen cargada. Lista para procesar.")
        else:
            self.lbl_estado.set_error("No se pudo leer la imagen.")

    def _iniciar_procesamiento(self):
        if self.worker is not None and self.worker.isRunning():
            return

        snr = self.spin_snr.value()
        if self.spin_snr.specialValueText() == "Sin ruido" and snr == 0:
            snr = None

        flujos = {0: "ambos", 1: "wav", 2: "directo"}
        kwargs = {
            "foto_path": self.ruta_foto,
            "salida": "salida_desafio4",
            "mod": self.combo_mod.currentText(),
            "bits": self.spin_bits.value(),
            "ancho": self.spin_ancho.value(),
            "fs": self.spin_fs.value(),
            "baud": float(self.spin_baud.value()),
            "snr": snr,
            "reproducir_audio": self.chk_audio.isChecked(),
            "mostrar_graficas": self.chk_graficas.isChecked(),
            "escuchar_seg": 8,
            "retener": 10,
            "calidad_webp": self.spin_calidad.value(),
            "flujo": flujos[self.combo_flujo.currentIndex()],
        }

        self._estado_procesando(True)
        self.worker = PipelineWorker(mode="send", **kwargs)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _estado_procesando(self, activo):
        enabled = not activo
        self.btn_procesar.setEnabled(enabled)
        self.btn_seleccionar.setEnabled(enabled)
        self.combo_mod.setEnabled(enabled)
        self.spin_bits.setEnabled(enabled)
        self.spin_ancho.setEnabled(enabled)
        self.spin_fs.setEnabled(enabled)
        self.spin_baud.setEnabled(enabled)
        self.spin_snr.setEnabled(enabled)
        self.chk_audio.setEnabled(enabled)
        self.chk_graficas.setEnabled(enabled)
        self.combo_flujo.setEnabled(enabled)
        self.spin_calidad.setEnabled(enabled)
        self.btn_preset_rapido.setEnabled(enabled)
        self.btn_preset_calidad.setEnabled(enabled)
        self.btn_preset_ruidoso.setEnabled(enabled)
        self.btn_preset_personalizado.setEnabled(enabled)

        if not activo:
            self.progreso.setValue(0)
            self.lbl_estado.set_text("Procesando...")
        else:
            self.btn_abrir_carpeta.setEnabled(False)
            self.btn_audio_mod.setEnabled(False)
            self.btn_audio_demo.setEnabled(False)

    def _on_progress(self, stage, message, percent):
        self.progreso.setValue(int(percent))
        self.lbl_estado.set_text(message)

    def _on_finished(self, resultado):
        self.resultado = resultado
        self._estado_procesando(False)

        self.panel_filtrada.viewer.set_image(resultado["imagen_filtrada"], max_display=700)
        self.panel_reconstruida.viewer.set_image(resultado["imagen_reconstruida"], max_display=700)

        self.lbl_metricas.setText(
            f"MSE: {resultado['mse']:.2f}   "
            f"PSNR: {resultado['psnr']:.1f} dB   "
            f"BER: {resultado['ber']:.2e}   "
            f"Errores: {resultado['errores_bit']:,}\n"
            f"Capas WebP: {resultado['tam_webp_kb']:.1f} KB   "
            f"ZIP directo: {resultado['tam_zip_directo_kb']:.1f} KB"
        )

        self.btn_abrir_carpeta.setEnabled(True)
        self.btn_audio_mod.setEnabled(True)
        self.btn_audio_demo.setEnabled(True)

        self.lbl_estado.set_ok("Proceso completado exitosamente")

        zip_wav = resultado.get("ruta_zip") or "No generado (elige el flujo WAV o Ambos)"
        zip_directo = resultado.get("ruta_zip_directo") or "No generado (elige el flujo WebP o Ambos)"
        QMessageBox.information(
            self, "Proceso completado",
            f"Imagen reconstruida:\n{resultado['ruta_png']}\n\n"
            f"ZIP con señal modulada:\n{zip_wav}\n\n"
            f"ZIP con capas WebP comprimidas:\n{zip_directo}\n\n"
            f"MSE={resultado['mse']:.2f}, PSNR={resultado['psnr']:.1f} dB, BER={resultado['ber']:.2e}"
        )

    def _on_error(self, mensaje):
        self._estado_procesando(False)
        self.lbl_estado.set_error(mensaje)
        QMessageBox.critical(self, "Error", mensaje)

    def _abrir_carpeta(self):
        if not self.resultado:
            return
        ruta = self.resultado["salida"]
        if hasattr(os, "startfile"):
            os.startfile(ruta)

    def _reproducir_audio_modulado(self):
        if not self.resultado:
            return
        self._reproducir_archivo(self.resultado["ruta_mod_wav"])

    def _reproducir_audio_demodulado(self):
        if not self.resultado:
            return
        self._reproducir_archivo(self.resultado["ruta_audio_demo"])

    def _reproducir_archivo(self, ruta):
        try:
            if hasattr(os, "startfile"):
                os.startfile(ruta)
        except Exception as e:
            QMessageBox.information(self, "Audio", f"No se pudo reproducir:\n{ruta}\n\n{e}")
