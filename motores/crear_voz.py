#!/usr/bin/env python3
"""Crea voces nuevas para Juglar a partir de una descripción (Qwen3-TTS VoiceDesign).

Uso: crear_voz.py TRABAJOS.json
  TRABAJOS.json: [{"id": "anciano", "label": "Anciano", "descripcion": "Anciano de unos 75 años…", "semilla": 1,
                   "texto": "frase de referencia (opcional, 7-10 s)"}, …]
Cada voz queda en <JUGLAR_DATA>/voces/<id>/ (ref.wav, ref.txt, meta.json) lista para usarse como cualquier otra.
Se ejecuta con el Python del entorno de Qwen (<JUGLAR_DATA>/qwen). Por stdout: una línea JSON por voz.
"""
import json
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
_OUT = os.fdopen(os.dup(1), "w")   # las librerías escriben en stdout: se manda a stderr y el progreso va por aquí
os.dup2(2, 1)
sys.stdout = sys.stderr

import soundfile as sf  # noqa: E402
import torch  # noqa: E402
from qwen_tts import Qwen3TTSModel  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "juglar"))
import rutas  # noqa: E402

VOCES = rutas.VOCES
# Texto corto: la referencia debe durar ~7-10 s (una más larga agota la memoria de la GPU al usarla)
TEXTO = "Aquella mañana, el pueblo despertó envuelto en una niebla espesa. Clara abrió la ventana, respiró hondo y sonrió."


def emit(**kw):
    _OUT.write(json.dumps(kw, ensure_ascii=False) + "\n")
    _OUT.flush()


def main():
    trabajos = json.loads(Path(sys.argv[1]).read_text())
    emit(type="start", total=len(trabajos))
    model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", device_map="cuda:0",
                                          dtype=torch.bfloat16)
    for n, job in enumerate(trabajos, 1):
        try:
            torch.manual_seed(int(job.get("semilla", 1234)))
            texto = job.get("texto") or TEXTO   # una frase dicha por el personaje le da su carácter a la voz
            wavs, sr = model.generate_voice_design(text=texto, language="Spanish", instruct=job["descripcion"])
            dest = VOCES / job["id"]
            dest.mkdir(parents=True, exist_ok=True)
            sf.write(dest / "ref.wav", wavs[0], sr)
            (dest / "ref.txt").write_text(texto)
            (dest / "meta.json").write_text(json.dumps(
                {"label": job.get("label", job["id"]), "descripcion": job["descripcion"]}, ensure_ascii=False, indent=1))
            emit(type="voz", id=job["id"], n=n, total=len(trabajos), segundos=len(wavs[0]) / sr)
        except Exception as e:  # noqa: BLE001
            emit(type="error", id=job.get("id"), n=n, message=str(e)[-300:])
    emit(type="done")


if __name__ == "__main__":
    main()
