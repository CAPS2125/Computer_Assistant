import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import comandos  # noqa: E402


@pytest.fixture
def asistente(monkeypatch):
    """Comandos reales de config.json, con los efectos secundarios interceptados."""
    efectos = {"urls": [], "run": [], "kill": []}
    monkeypatch.setattr(comandos, "ES_WINDOWS", True)
    monkeypatch.setattr(comandos.webbrowser, "open", lambda u, *a, **k: efectos["urls"].append(u))
    monkeypatch.setattr(comandos.subprocess, "Popen", lambda a, **k: efectos["run"].append(a))
    monkeypatch.setattr(comandos.subprocess, "run", lambda a, **k: efectos["kill"].append(a))
    a = comandos.Comandos(comandos.cargar_config())
    a.efectos = efectos
    return a


def test_normalizar():
    assert comandos.normalizar("¡Apágate!") == "apagate"


@pytest.mark.parametrize("frase,esperado", [
    ("hola", "saludo"),
    ("abre la calculadora por favor", "calculadora"),
    ("abre el bloc de notas", "notas"),
    ("quiero programar", "programar"),
    ("abre claudio", "claude"),
    ("apágate", "apagar"),
])
def test_interpretar(asistente, frase, esperado):
    assert asistente.interpretar(frase)["id"] == esperado


def test_no_coincide_dentro_de_otra_palabra(asistente):
    assert asistente.interpretar("chola") is None


def test_texto_desconocido(asistente):
    res = asistente.procesar("blablabla")
    assert res.estado == "dudosa" and not res.hablar and not res.entendido


def test_calculadora_se_lanza(asistente):
    res = asistente.procesar("calculadora")
    assert res.entendido and ["calc.exe"] in asistente.efectos["run"]


def test_limpiar_pide_confirmacion(asistente):
    res = asistente.procesar("limpiar")
    assert res.espera_respuesta and not asistente.efectos["kill"]
    res = asistente.procesar("sí")
    assert res.estado == "feliz"
    cerrados = [c[2] for c in asistente.efectos["kill"]]
    assert "msedge.exe" in cerrados
    assert all("/f" not in c for c in asistente.efectos["kill"])  # cierre amable


def test_limpiar_cancelado(asistente):
    asistente.procesar("limpiar")
    res = asistente.procesar("no")
    assert res.mensaje == "Cancelado" and not asistente.efectos["kill"]


def test_confirmacion_expira(asistente, monkeypatch):
    asistente.procesar("limpiar")
    cmd, _ = asistente.pendiente
    asistente.pendiente = (cmd, 0)  # ya venció
    asistente.procesar("sí")
    assert not asistente.efectos["kill"]


def test_apagar_marca_apagado(asistente):
    assert asistente.procesar("apagate").apagar is True
