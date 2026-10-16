"""Motor de comandos de Computer_Assistant v0.3.

No depende de la interfaz ni del audio, así que se puede probar con pytest.
Los comandos viven en config.json; aquí solo está la lógica para interpretarlos y ejecutarlos.
"""
import json
import logging
import random
import re
import subprocess
import sys
import time
import unicodedata
import webbrowser
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

log = logging.getLogger(__name__)

ES_WINDOWS = sys.platform == "win32"
SIN_VENTANA = 0x08000000 if ES_WINDOWS else 0  # CREATE_NO_WINDOW
RUTA_CONFIG = Path(__file__).with_name("config.json")

AFIRMATIVO = {"si", "confirmo", "dale", "claro", "adelante", "ok"}
NEGATIVO = {"no", "cancela", "cancelar", "detente"}
TIEMPO_CONFIRMACION_S = 10

DEFAULTS = {
    "idioma": "es-MX",
    "palabras_activacion": ["asistente"],
    "ventana_activa_s": 8,
    "ventana_seguimiento_s": 0,
    "aburrida_s": 45,
    "burbuja_s": 4,
    "tts": {"activo": True, "velocidad": 165},
    "comandos": [],
}


def cargar_config(ruta=RUTA_CONFIG):
    """Lee config.json y completa con valores por defecto lo que falte."""
    with open(ruta, encoding="utf-8") as f:
        usuario = json.load(f)
    cfg = {**DEFAULTS, **usuario}
    cfg["tts"] = {**DEFAULTS["tts"], **usuario.get("tts", {})}
    return cfg


def normalizar(texto):
    """Minúsculas, sin acentos ni signos: 'Apágate!' -> 'apagate'."""
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _coincide(palabra, token):
    """Igualdad exacta; en palabras largas tolera pequeños errores del reconocedor."""
    if palabra == token:
        return True
    return len(palabra) >= 5 and SequenceMatcher(None, palabra, token).ratio() >= 0.85


def _puntaje(tokens_frase, tokens_texto):
    """Cuántas palabras aporta la frase si TODAS están en el texto; 0 si no coincide."""
    if all(any(_coincide(p, t) for t in tokens_texto) for p in tokens_frase):
        return len(tokens_frase)
    return 0


@dataclass
class Resultado:
    estado: str = "normal"          # estado de la mascota: feliz, dudosa, escuchando...
    mensaje: str = ""               # texto de la burbuja (y de la voz si hablar=True)
    hablar: bool = False
    apagar: bool = False
    espera_respuesta: bool = False  # True si hay una confirmación pendiente
    entendido: bool = False


class Comandos:
    def __init__(self, config):
        self.cmds = config.get("comandos", [])
        self.pendiente = None  # (comando, expira)

    # --- interpretación (pura, sin efectos secundarios) ---
    def interpretar(self, texto):
        tokens = normalizar(texto).split()
        mejor, mejor_p = None, 0
        for cmd in self.cmds:
            for frase in cmd.get("palabras", []):
                p = _puntaje(normalizar(frase).split(), tokens)
                if p > mejor_p:  # en empate gana el primero de config.json
                    mejor, mejor_p = cmd, p
        return mejor

    # --- flujo completo ---
    def procesar(self, texto):
        norm = normalizar(texto)

        if self.pendiente:
            cmd, expira = self.pendiente
            self.pendiente = None
            if time.monotonic() <= expira:
                palabras = set(norm.split())
                if palabras & AFIRMATIVO:
                    return self._ejecutar(cmd)
                if palabras & NEGATIVO:
                    return Resultado("normal", "Cancelado", hablar=True, entendido=True)

        cmd = self.interpretar(norm)
        if cmd is None:
            return Resultado("dudosa", f"No entendí '{norm}'")

        if cmd.get("confirmar"):
            self.pendiente = (cmd, time.monotonic() + TIEMPO_CONFIRMACION_S)
            return Resultado("escuchando", "¿Seguro? Di sí o no", hablar=True,
                             espera_respuesta=True, entendido=True)

        return self._ejecutar(cmd)

    # --- ejecución ---
    def _ejecutar(self, cmd):
        for url in cmd.get("urls", []):
            try:
                webbrowser.open(url)
            except Exception:
                log.exception("No se pudo abrir %s", url)
        for args in cmd.get("run", []):
            self._lanzar(args)
        for exe in cmd.get("kill", []):
            self._cerrar(exe, cmd.get("forzar", False))

        mensaje = cmd.get("mensaje") or random.choice(cmd.get("respuestas", ["Listo"]))
        log.info("Comando '%s' ejecutado", cmd.get("id"))
        return Resultado("feliz", mensaje, hablar=True,
                         apagar=cmd.get("apagar", False), entendido=True)

    @staticmethod
    def _lanzar(args):
        try:
            subprocess.Popen(args, creationflags=SIN_VENTANA)
        except OSError:
            log.exception("No se pudo lanzar %s", args)

    @staticmethod
    def _cerrar(exe, forzar):
        """Cierre amable por defecto: la app puede preguntar si guardar cambios."""
        if not ES_WINDOWS:
            log.warning("Cerrar '%s' solo está implementado para Windows", exe)
            return
        orden = ["taskkill", "/im", exe] + (["/f"] if forzar else [])
        try:
            subprocess.run(orden, capture_output=True, creationflags=SIN_VENTANA)
        except OSError:
            log.exception("No se pudo cerrar %s", exe)
