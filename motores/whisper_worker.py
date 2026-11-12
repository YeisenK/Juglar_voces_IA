#!/usr/bin/env python3
"""Transcribe fragmentos de audio con Whisper (CPU) para que md2audio compruebe lo que dijo la voz.

Se ejecuta con el Python del entorno de Whisper (<JUGLAR_DATA>/whisper).
Entrada (stdin): una línea JSON {"id": n, "rate": 24000, "bytes": N} seguida de N bytes de PCM s16le mono.
Salida (stdout): una línea JSON {"id": n, "text": "..."} por petición, en orden.
"""
import json
import os
import subprocess
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
_OUT = os.fdopen(os.dup(1), "w")
os.dup2(2, 1)
sys.stdout = sys.stderr

import numpy as np  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402


def main():
    model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8",
                         cpu_threads=int(os.environ.get("WHISPER_THREADS", "6")))
    print("listo", file=sys.stderr, flush=True)
    inp = sys.stdin.buffer
    while True:
        line = inp.readline()
        if not line:
            break
        req = json.loads(line)
        pcm = inp.read(req["bytes"])
        try:
            a = np.frombuffer(subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", str(req["rate"]), "-ac", "1", "-i", "-",
                 "-f", "f32le", "-ar", "16000", "-"], input=pcm, capture_output=True, check=True).stdout, np.float32)
            segs, _ = model.transcribe(a, language="es", beam_size=1, condition_on_previous_text=False,
                                       temperature=0.0)
            text = " ".join(s.text.strip() for s in segs)
        except Exception as e:  # noqa: BLE001
            print(f"fallo al transcribir: {e}", file=sys.stderr, flush=True)
            text = None
        _OUT.write(json.dumps({"id": req["id"], "text": text}, ensure_ascii=False) + "\n")
        _OUT.flush()


if __name__ == "__main__":
    main()
