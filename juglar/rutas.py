"""Dónde vive cada cosa de Juglar. Todo se puede mover con variables de entorno.

El código va en el repositorio; los entornos de Python, los modelos y las voces, en JUGLAR_DATA
(por defecto ~/.local/share/juglar); tus ajustes, en ~/.config/juglar.
"""
import os
from pathlib import Path


def _xdg(var, default):
    return Path(os.environ.get(var) or Path.home() / default)


APP = Path(__file__).resolve().parent          # este directorio: el código de la app
RAIZ = APP.parent                              # el repositorio
MOTORES = RAIZ / "motores"                     # procesos que corren en los entornos de Qwen y Whisper

DATA = Path(os.environ.get("JUGLAR_DATA") or _xdg("XDG_DATA_HOME", ".local/share") / "juglar")
CONFIG = _xdg("XDG_CONFIG_HOME", ".config") / "juglar"
STATE = _xdg("XDG_STATE_HOME", ".local/state") / "juglar"
CACHE = _xdg("XDG_CACHE_HOME", ".cache") / "juglar"

VENV_PY = DATA / "venv/bin/python"             # Piper y Kokoro
QWEN_PY = DATA / "qwen/bin/python"             # Qwen3-TTS
WHISPER_PY = DATA / "whisper/bin/python"       # revisión con Whisper
ACESTEP = DATA / "acestep"                     # ACE-Step 1.5 (música), con su entorno en .venv y modelos en checkpoints
ACESTEP_PY = ACESTEP / ".venv/bin/python"
MUSICA = Path(os.environ.get("JUGLAR_MUSICA") or Path.home() / "Música" / "Juglar")  # canciones generadas
PIPER_VOCES = DATA / "piper-voces"             # modelos .onnx de Piper
KOKORO_DIR = DATA / "kokoro"                   # kokoro-v1.0.onnx y voices-v1.0.bin
VOCES = DATA / "voces"                         # voces de Qwen, personajes y ajustes del audiolibro
PRUEBAS = DATA / "pruebas"                     # pruebas de voz ya generadas

DICCIONARIO = CONFIG / "pronunciacion.txt"     # «Palabra = cómo se lee»
PRUEBA_VOZ = CONFIG / "prueba_voz.txt"         # texto estándar para probar voces
