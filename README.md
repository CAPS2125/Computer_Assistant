# Computer_Assistant v0.3

Mascota de escritorio controlada por voz (PyQt6). Windows como objetivo principal.

## Instalar y correr
    pip install -r requirements.txt
    python petbrain3.py

Di **«asistente»** y luego el comando (en la misma frase o tras el "Dime..."). Clic derecho sobre la mascota para salir.

## Estructura
- `petbrain3.py` — ventana, máquina de estados (`PetBrain`) y arranque
- `voz.py` — `Hablador` (TTS en cola) y `Escucha` (STT + palabra de activación)
- `comandos.py` — motor de comandos, sin dependencias de UI/audio
- `config.json` — ajustes y lista de comandos
- `tests/` — `pytest`

## Agregar un comando (solo config.json)
    { "id": "spotify", "palabras": ["musica", "spotify"],
      "urls": ["https://open.spotify.com"], "mensaje": "Abriendo Spotify" }
Campos opcionales: `run` (lista de comandos), `kill` + `forzar`, `confirmar`, `respuestas`, `apagar`.

## Límites conocidos
- El reconocimiento usa Google (necesita internet).
- La palabra de activación se cambia en `palabras_activacion`.
- Cerrar apps (`kill`) solo funciona en Windows.
