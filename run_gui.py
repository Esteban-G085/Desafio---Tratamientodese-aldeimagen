#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point para lanzar la interfaz gráfica PyQt6 del desafío 4."""

import sys

from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Desafío 4 - Tratamiento de señal de imagen")
    ventana = MainWindow()
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
