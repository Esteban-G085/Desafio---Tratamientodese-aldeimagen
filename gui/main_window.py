"""Ventana principal de la aplicación PyQt6."""

import os

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QScrollArea, QWidget, QVBoxLayout
)
from PyQt6.QtCore import QFile, QTextStream

from gui.process_tab import ProcessTab
from gui.receive_tab import ReceiveTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Desafío 4 - Tratamiento de señal de imagen")
        self.resize(1300, 900)
        self.setMinimumSize(900, 700)

        # Scroll area principal para que todo el contenido sea accesible
        # cuando la ventana se hace pequeña
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: #fafafa; }")
        self.setCentralWidget(self.scroll_area)

        # Contenedor interior con las pestañas
        self.contenedor = QWidget()
        self.scroll_area.setWidget(self.contenedor)

        layout = QVBoxLayout(self.contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tab_procesar = ProcessTab()
        self.tab_recibir = ReceiveTab()
        self.tabs.addTab(self.tab_procesar, "Procesar (envía)")
        self.tabs.addTab(self.tab_recibir, "Recibir (compañero)")
        layout.addWidget(self.tabs)

        self._aplicar_estilos()

    def _aplicar_estilos(self):
        """Carga y aplica la hoja de estilos QSS."""
        ruta_qss = os.path.join(os.path.dirname(__file__), "styles.qss")
        archivo = QFile(ruta_qss)
        if archivo.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            stream = QTextStream(archivo)
            estilo = stream.readAll()
            self.setStyleSheet(estilo)
            archivo.close()
