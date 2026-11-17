"""Worker en segundo plano (QThread) para ejecutar el pipeline sin congelar la GUI."""

from PyQt6.QtCore import QThread, pyqtSignal

from core.pipeline import ImageSignalPipeline


class PipelineWorker(QThread):
    progress = pyqtSignal(str, str, float)   # stage, message, percent
    finished = pyqtSignal(dict)               # resultados del pipeline
    error = pyqtSignal(str)                   # mensaje de error

    def __init__(self, mode, **kwargs):
        super().__init__()
        self.mode = mode
        self.kwargs = kwargs
        self.pipeline = ImageSignalPipeline(progress_callback=self._on_progress)

    def _on_progress(self, stage, message, percent):
        self.progress.emit(stage, message, percent)

    def run(self):
        try:
            if self.mode == "send":
                resultado = self.pipeline.run_send(**self.kwargs)
            elif self.mode == "receive":
                resultado = self.pipeline.run_receive(**self.kwargs)
            else:
                raise ValueError(f"Modo desconocido: {self.mode}")
            self.finished.emit(resultado)
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))
