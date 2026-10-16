"""Voz de Computer_Assistant v0.3: salida (TTS en cola) y entrada (STT con palabra de activación)."""
import logging
import queue
import re
import threading
import time

import pyttsx3
import speech_recognition as sr
from PyQt6.QtCore import QThread, pyqtSignal

from comandos import normalizar

log = logging.getLogger(__name__)

_PATRON_ES = re.compile(r"(?<![a-z])es[-_](mx|es|us|ar|co|cl)", re.I)


def _voz_en_espanol(motor):
    """Elige una voz en español mirando el NOMBRE y el final del ID (no la ruta completa)."""
    candidatas = []
    for v in motor.getProperty("voices"):
        nombre = v.name or ""
        ident = (v.id or "").replace("\\", "/").split("/")[-1]
        if (re.search(r"spanish|espa[ñn]ol", nombre, re.I)
                or _PATRON_ES.search(nombre) or _PATRON_ES.search(ident)):
            prioridad = 0 if re.search(r"mx|mexic", nombre + ident, re.I) else 1
            candidatas.append((prioridad, v.id))
    return min(candidatas)[1] if candidatas else None


class Hablador(threading.Thread):
    """Un solo hilo y un solo motor TTS: las frases se encolan en vez de solaparse."""

    def __init__(self, velocidad=165, activo=True):
        super().__init__(name="Hablador", daemon=True)
        self.velocidad = velocidad
        self.activo = activo
        self._cola = queue.Queue()
        self._pendientes = 0
        self._lock = threading.Lock()

    @property
    def ocupado(self):
        with self._lock:
            return self._pendientes > 0

    def decir(self, texto):
        if not self.activo or not texto:
            return
        with self._lock:
            self._pendientes += 1
        self._cola.put(texto)

    def apagar(self):
        self._cola.put(None)

    def run(self):
        try:
            motor = pyttsx3.init()
            motor.setProperty("rate", self.velocidad)
            voz = _voz_en_espanol(motor)
            if voz:
                motor.setProperty("voice", voz)
            else:
                log.warning("No hay voz en español instalada; se usará la predeterminada")
        except Exception:
            log.exception("No se pudo iniciar la voz; se desactiva el TTS")
            self.activo = False
            with self._lock:
                self._pendientes = 0
            return

        while True:
            texto = self._cola.get()
            if texto is None:
                break
            try:
                motor.say(texto)
                motor.runAndWait()
            except Exception:
                log.exception("Error al hablar")
            finally:
                with self._lock:
                    self._pendientes -= 1


class Escucha(QThread):
    """Escucha el micrófono. Solo actúa tras la palabra de activación (o dentro de una ventana activa)."""

    estado = pyqtSignal(str, str)   # (estado de la mascota, texto de burbuja)
    resultado = pyqtSignal(object)  # Resultado de comandos.procesar

    def __init__(self, comandos, hablador, cfg):
        super().__init__()
        self.comandos = comandos
        self.hablador = hablador
        self.idioma = cfg["idioma"]
        self.palabras = [normalizar(p) for p in cfg["palabras_activacion"]]
        self.ventana = cfg["ventana_activa_s"]
        self.seguimiento = cfg["ventana_seguimiento_s"]
        self._parar = threading.Event()
        self._activo_hasta = 0.0
        self._ultimo_aviso_red = 0.0

    def detener(self):
        self._parar.set()

    def run(self):
        r = sr.Recognizer()
        r.dynamic_energy_threshold = True
        r.pause_threshold = 0.8
        try:
            with sr.Microphone() as fuente:
                r.adjust_for_ambient_noise(fuente, duration=1)
        except Exception:
            log.exception("No se pudo abrir el micrófono")
            self.estado.emit("dudosa", "No encuentro el micrófono")
            return

        while not self._parar.is_set():
            self._revisar_ventana()
            self._esperar_silencio()
            if self._parar.is_set():
                break
            try:
                with sr.Microphone() as fuente:
                    audio = r.listen(fuente, timeout=3, phrase_time_limit=7)
            except sr.WaitTimeoutError:
                continue
            except Exception:
                log.exception("Error de micrófono")
                self._parar.wait(2)
                continue

            try:
                texto = r.recognize_google(audio, language=self.idioma)
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                self._avisar_red(e)
                self._parar.wait(3)
                continue
            self._atender(texto)

    # --- piezas internas ---
    def _esperar_silencio(self):
        """No escucha mientras la mascota habla (evita que se oiga a sí misma)."""
        hablo = False
        while self.hablador.ocupado and not self._parar.is_set():
            hablo = True
            self.msleep(100)
        if hablo:
            self.msleep(400)  # cola del eco de la sala

    def _revisar_ventana(self):
        if self._activo_hasta and time.monotonic() > self._activo_hasta:
            self._activo_hasta = 0.0
            self.estado.emit("normal", "")

    def _quitar_activacion(self, norm):
        for p in self.palabras:
            m = re.search(rf"\b{re.escape(p)}\b", norm)
            if m:
                return norm[m.end():].strip()
        return None

    def _atender(self, texto):
        norm = normalizar(texto)
        log.info("Oído: %s", norm)

        if time.monotonic() < self._activo_hasta:
            orden = norm
        else:
            orden = self._quitar_activacion(norm)
            if orden is None:
                return  # no dijo la palabra de activación: se ignora
            if not orden:
                self._activo_hasta = time.monotonic() + self.ventana
                self.estado.emit("escuchando", "Dime...")
                self.hablador.decir("Dime")
                return

        res = self.comandos.procesar(orden)
        espera = self.ventana if res.espera_respuesta else self.seguimiento
        self._activo_hasta = time.monotonic() + espera if espera > 0 else 0.0
        if res.hablar:
            self.hablador.decir(res.mensaje)  # se encola ya, antes de volver a escuchar
        self.resultado.emit(res)

    def _avisar_red(self, error):
        log.warning("Reconocimiento de voz no disponible: %s", error)
        if time.monotonic() - self._ultimo_aviso_red > 30:
            self._ultimo_aviso_red = time.monotonic()
            self.estado.emit("dudosa", "Sin conexión para la voz")
