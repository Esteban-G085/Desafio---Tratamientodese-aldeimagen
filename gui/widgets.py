"""Widgets reutilizables para la GUI del desafío 4."""

import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QPushButton, QScrollArea, QSizePolicy


class ImageViewer(QScrollArea):
    """Visor de imagen con scroll. Nunca recorta la imagen."""

    def __init__(self, parent=None, placeholder_text="Sin imagen"):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("QScrollArea { border: 1px solid #bdbdbd; background: #f5f5f5; }")
        self.setMinimumSize(260, 200)

        self.label = QLabel(placeholder_text)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.label.setMinimumSize(240, 180)
        self.setWidget(self.label)

        self._current_pixmap = None

    def set_image(self, img, max_display=None):
        """Muestra una imagen numpy. Si es más grande que el visor, aparece scroll."""
        if img is None:
            self.clear()
            return

        arr = np.asarray(img)
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=2)
        arr = np.clip(arr, 0, 255).astype(np.uint8)

        h, w, ch = arr.shape
        bytes_per_line = ch * w
        qimg = QImage(arr.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg)

        if max_display:
            pix = pix.scaled(
                max_display, max_display,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        self._current_pixmap = pix
        self.label.setPixmap(pix)
        self.label.setText("")
        self.label.adjustSize()
        self.update()

    def clear(self):
        self._current_pixmap = None
        self.label.clear()
        self.label.setText("Sin imagen")
        self.label.adjustSize()
        self.update()


class StatusLabel(QLabel):
    """Etiqueta de estado con colores."""

    def __init__(self, texto="Listo", parent=None):
        super().__init__(texto, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("color: #666666; font-style: italic; padding: 6px;")
        self.setMinimumHeight(24)

    def set_text(self, texto=""):
        self.setText(texto or "Listo")
        self.setStyleSheet("color: #666666; font-style: italic; padding: 6px;")

    def set_ok(self, texto=""):
        self.setText(texto or "Listo")
        self.setStyleSheet("color: #2e7d32; font-weight: bold; padding: 6px;")

    def set_warning(self, texto=""):
        self.setText(texto or "Atención")
        self.setStyleSheet("color: #f9a825; font-weight: bold; padding: 6px;")

    def set_error(self, texto=""):
        self.setText(texto or "Error")
        self.setStyleSheet("color: #c62828; font-weight: bold; padding: 6px;")


class PresetButton(QPushButton):
    """Botón para aplicar una configuración base predefinida."""

    def __init__(self, nombre, descripcion, valores, parent=None):
        super().__init__(parent)
        self.valores = valores
        self.setText(f"{nombre}\n{descripcion}")
        self.setMinimumHeight(55)
        self.setStyleSheet(
            "QPushButton { "
            "   background-color: #e3f2fd; "
            "   color: #1565c0; "
            "   font-weight: bold; "
            "   font-size: 11px; "
            "   border: 1px solid #90caf9; "
            "   border-radius: 6px; "
            "   text-align: left; "
            "   padding: 6px 10px; "
            "} "
            "QPushButton:hover { "
            "   background-color: #bbdefb; "
            "   border-color: #64b5f6; "
            "} "
            "QPushButton:pressed { "
            "   background-color: #90caf9; "
            "}"
        )
