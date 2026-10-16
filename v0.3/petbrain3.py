"""Computer_Assistant v0.3 — mascota de escritorio controlada por voz."""
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

from comandos import Comandos, cargar_config
from voz import Escucha, Hablador

log = logging.getLogger("petbrain")

TRANSITORIOS = {"feliz": 2.5, "dudosa": 2.5}  # estados que vuelven solos a "normal"


class PetBrain:
    """Máquina de estados: normal, escuchando, feliz, dudosa, aburrida."""

    def __init__(self, aburrida_s):
        self.aburrida_s = aburrida_s
        self.estado = "normal"
        self._desde = time.monotonic()
        self._ultima_actividad = time.monotonic()

    def registrar_actividad(self):
        """Actividad real: palabra de activación, comando o interacción con el mouse."""
        self._ultima_actividad = time.monotonic()
        if self.estado == "aburrida":
            self.poner("normal", forzar=True)

    def poner(self, nuevo, forzar=False):
        if self.estado == "aburrida" and not forzar:
            return  # solo la actividad real la despierta
        if nuevo != self.estado:
            self.estado = nuevo
            self._desde = time.monotonic()

    def tick(self):
        """Devuelve el nuevo estado si cambió por tiempo, o None."""
        ahora = time.monotonic()
        if self.estado in TRANSITORIOS and ahora - self._desde > TRANSITORIOS[self.estado]:
            self.poner("normal")
            return self.estado
        if self.estado == "normal" and ahora - self._ultima_actividad > self.aburrida_s:
            self.poner("aburrida")
            return self.estado
        return None


class MascotWindow(QWidget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(220, 190)
        self._colocar_abajo_derecha()

        self.brain = PetBrain(cfg["aburrida_s"])
        self.bubble_text = f"Di «{cfg['palabras_activacion'][0]}»"
        self.show_bubble = True
        self.old_pos = None

        self.bubble_timer = QTimer(self, singleShot=True)
        self.bubble_timer.timeout.connect(self._ocultar_burbuja)
        self.bubble_timer.start(cfg["burbuja_s"] * 1000)

        self.reloj = QTimer(self)
        self.reloj.timeout.connect(self._tick)
        self.reloj.start(500)

        self.hablador = Hablador(cfg["tts"]["velocidad"], cfg["tts"]["activo"])
        self.hablador.start()
        self.escucha = Escucha(Comandos(cfg), self.hablador, cfg)
        self.escucha.estado.connect(self.on_estado)
        self.escucha.resultado.connect(self.on_resultado)
        self.escucha.start()

        QApplication.instance().aboutToQuit.connect(self.cerrar_recursos)

    # --- ciclo de vida ---
    def _colocar_abajo_derecha(self):
        geo = QApplication.primaryScreen().availableGeometry()
        self.move(geo.right() - self.width() - 30, geo.bottom() - self.height() - 30)

    def cerrar_recursos(self):
        self.escucha.detener()
        self.escucha.wait(4000)
        self.hablador.apagar()

    # --- señales del hilo de voz ---
    def on_estado(self, estado, texto):
        if estado == "escuchando":
            self.brain.registrar_actividad()
        self.brain.poner(estado)
        if texto:
            self._mostrar(texto, persistente=(estado == "escuchando"))
        elif estado == "normal":
            self._ocultar_burbuja()
        self.update()

    def on_resultado(self, res):
        self.brain.registrar_actividad()
        self.brain.poner(res.estado, forzar=True)
        self._mostrar(res.mensaje, persistente=res.espera_respuesta)
        if res.apagar:
            QTimer.singleShot(2500, QApplication.quit)

    # --- burbuja ---
    def _mostrar(self, texto, persistente=False):
        self.bubble_text = texto
        self.show_bubble = True
        if persistente:
            self.bubble_timer.stop()
        else:
            self.bubble_timer.start(self.cfg["burbuja_s"] * 1000)
        self.update()

    def _ocultar_burbuja(self):
        self.show_bubble = False
        self.update()

    def _tick(self):
        nuevo = self.brain.tick()
        if nuevo == "aburrida":
            self._mostrar("¿Sigues ahí? 😴")
        if nuevo:
            self.update()

    # --- dibujo ---
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.show_bubble and self.bubble_text:
            p.setBrush(QColor(255, 255, 255))
            p.setPen(QColor(200, 200, 200))
            p.drawRoundedRect(10, 10, 200, 55, 10, 10)
            p.setPen(QColor(45, 55, 72))
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            p.drawText(18, 14, 184, 47,
                       Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       self.bubble_text)

        p.setBrush(QColor(45, 55, 72))
        p.setPen(Qt.PenStyle.NoPen)
        e = self.brain.estado
        if e == "normal":
            p.drawEllipse(60, 95, 30, 45)
            p.drawEllipse(130, 95, 30, 45)
        elif e == "escuchando":
            p.drawEllipse(58, 90, 34, 50)
            p.drawEllipse(128, 90, 34, 50)
        elif e == "feliz":
            p.drawChord(60, 105, 30, 30, 0, 180 * 16)
            p.drawChord(130, 105, 30, 30, 0, 180 * 16)
        elif e == "dudosa":
            p.drawEllipse(60, 95, 30, 45)
            p.drawEllipse(135, 110, 22, 22)
        elif e == "aburrida":
            p.drawRect(60, 112, 30, 8)
            p.drawRect(130, 112, 30, 8)

    # --- mouse: arrastrar y menú ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.brain.registrar_actividad()
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("Salir").triggered.connect(QApplication.quit)
        menu.exec(event.globalPos())


def configurar_logging():
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    archivo = RotatingFileHandler(Path(__file__).with_name("asistente.log"),
                                  maxBytes=500_000, backupCount=2, encoding="utf-8")
    consola = logging.StreamHandler()
    for h in (archivo, consola):
        h.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[archivo, consola])


def main():
    configurar_logging()
    app = QApplication(sys.argv)
    pet = MascotWindow(cargar_config())
    pet.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
