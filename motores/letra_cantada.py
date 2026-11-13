#!/usr/bin/env python3
"""Mide cuánta letra se canta de verdad en una o varias canciones (con Whisper).

Uso: letra_cantada.py LETRA.txt CANCIÓN.mp3 [CANCIÓN2.mp3 …]

Se ejecuta con el Python del entorno de Whisper (<JUGLAR_DATA>/whisper). Para cada canción imprime una línea JSON:
  {"audio": "...", "cobertura": 0.83, "texto": "lo que entendió Whisper"}
«cobertura» es la parte de las palabras de la letra que aparecen cantadas y en orden (0 a 1): sirve para comparar
tomas de la misma letra y quedarse con la que no se salta versos. Whisper no es perfecto con música, así que el
número exacto importa menos que la comparación entre tomas.
"""
import difflib
import json
import os
import re
import sys
import unicodedata

os.environ.setdefault("HF_HUB_OFFLINE", "1")
# las librerías CUDA de Whisper vienen en paquetes de pip: hay que añadirlas a LD_LIBRARY_PATH y volver a arrancar
if "LETRA_REEXEC" not in os.environ:
    try:
        import nvidia.cublas
        import nvidia.cudnn
        for mod in (nvidia.cublas, nvidia.cudnn):
            os.environ["LD_LIBRARY_PATH"] = (os.path.join(list(mod.__path__)[0], "lib") + ":"
                                             + os.environ.get("LD_LIBRARY_PATH", ""))
        os.environ["LETRA_REEXEC"] = "1"
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except ImportError:
        pass
_OUT = os.fdopen(os.dup(1), "w")
os.dup2(2, 1)
sys.stdout = sys.stderr


def palabras(t):
    t = re.sub(r"\[[^\]]*\]", " ", t)  # fuera etiquetas [Verse]
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w\s]|_", " ", t).split()


def cobertura(letra, texto):
    a, b = palabras(letra), palabras(texto)
    if not a:
        return 1.0
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sum(m.size for m in sm.get_matching_blocks()) / len(a)


def main():
    letra = open(sys.argv[1], encoding="utf-8").read()
    import subprocess
    import numpy as np
    from faster_whisper import WhisperModel
    modelos = {}

    def modelo(gpu):
        if gpu not in modelos:
            modelos[gpu] = (WhisperModel("large-v3-turbo", device="cuda", compute_type="float16") if gpu else
                            WhisperModel("large-v3-turbo", device="cpu", compute_type="int8",
                                         cpu_threads=int(os.environ.get("WHISPER_THREADS", "6"))))
        return modelos[gpu]

    def transcribir(pcm, gpu):
        segs, _ = modelo(gpu).transcribe(pcm, language=idioma, beam_size=1, condition_on_previous_text=False,
                                         temperature=0.0)
        return " ".join(s.text.strip() for s in segs)

    idioma = os.environ.get("IDIOMA", "es")
    gpu = True
    for audio in sys.argv[2:]:
        try:
            pcm = np.frombuffer(subprocess.run(["ffmpeg", "-loglevel", "error", "-i", audio, "-f", "f32le", "-ac", "1",
                                                "-ar", "16000", "-"], capture_output=True, check=True).stdout, np.float32)
            try:  # en la GPU si se puede (mucho más rápido); si no, en la CPU
                texto = transcribir(pcm, gpu)
            except Exception as e:  # noqa: BLE001
                if not gpu:
                    raise
                print(f"Whisper en la GPU falló ({e}); sigo en la CPU", file=sys.stderr)
                gpu = False
                texto = transcribir(pcm, gpu)
            res = {"audio": audio, "cobertura": round(cobertura(letra, texto), 3), "texto": texto}
        except Exception as e:  # noqa: BLE001
            res = {"audio": audio, "cobertura": None, "error": str(e)}
        _OUT.write(json.dumps(res, ensure_ascii=False) + "\n")
        _OUT.flush()


if __name__ == "__main__":
    main()
