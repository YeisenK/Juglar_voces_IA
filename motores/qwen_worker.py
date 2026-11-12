#!/usr/bin/env python3
"""Proceso de síntesis con Qwen3-TTS (modelo Base, clonación) para md2audio.

Uso: qwen_worker.py PERFIL [VELOCIDAD] [AJUSTES_JSON]
(AJUSTES_JSON: temperature, top_p, top_k, repetition_penalty, recortar_silencios)

Se ejecuta con el Python del entorno de Qwen (<JUGLAR_DATA>/qwen). Carga el modelo una vez y
fija la voz a partir de un perfil (ref.wav + ref.txt), así suena igual en todo el documento.

Protocolo por stdin/stdout:
  entrada: una línea JSON por petición: {"texts": ["frase 1", "frase 2", ...]}
  salida:  por cada texto, en orden: 8 bytes (longitud, little-endian) + PCM s16le mono 24 kHz
Los mensajes de estado van por stderr.
"""
import gc
import json
import os
import struct
import subprocess
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

# El audio sale por una copia privada de stdout; todo lo que impriman las librerías va a stderr
_AUDIO_OUT = os.fdopen(os.dup(1), "wb")
os.dup2(2, 1)
sys.stdout = sys.stderr

import numpy as np  # noqa: E402
import torch  # noqa: E402
from qwen_tts import Qwen3TTSModel  # noqa: E402

MODEL = os.environ.get("QWEN_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
LANGUAGE = "Spanish"


def atempo(pcm: bytes, rate: int, speed: float) -> bytes:
    """Cambia la velocidad sin alterar el tono (Qwen no tiene parámetro de velocidad)."""
    if abs(speed - 1.0) < 0.01 or not pcm:
        return pcm
    filters = []
    s = speed
    while s > 2.0:
        filters.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        filters.append("atempo=0.5")
        s /= 0.5
    filters.append(f"atempo={s:.4f}")
    return subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "-",
         "-af", ",".join(filters), "-f", "s16le", "-"],
        input=pcm, capture_output=True, check=True).stdout


GEN_KEYS = ("temperature", "top_p", "top_k", "repetition_penalty")
TOKENS_PER_CHAR = 3  # ~0,85 tokens/carácter al hablar (12,5 tokens/s); el triple como tope contra generaciones desbocadas


def trim_silence(w, sr, thresh=0.01, keep=0.05):
    """Quita el silencio sobrante al principio y al final; las pausas las decide md2audio."""
    idx = np.flatnonzero(np.abs(w) > thresh)
    if not idx.size:
        return w
    pad = int(sr * keep)
    return w[max(0, idx[0] - pad): idx[-1] + pad]


def main():
    profile = Path(sys.argv[1])
    speed = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    settings = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    voice_gen = settings.get("voces", {})   # muestreo de cada voz: {perfil: {temperature, top_p, ...}}
    cast = settings.get("personajes", {})   # personajes con nombre: {"@marta": {perfil, velocidad, temperature, ...}}
    for key, ficha in cast.items():
        voice_gen[key] = {k: ficha[k] for k in GEN_KEYS if k in ficha}

    def gen_for(name):
        g = {k: v for k, v in {**{k: settings.get(k) for k in GEN_KEYS}, **voice_gen.get(name or profile.name, {})}.items()
             if v is not None}
        if "temperature" in g:
            g["subtalker_temperature"] = g["temperature"]
        return g
    trim = settings.get("recortar_silencios", True)
    model = Qwen3TTSModel.from_pretrained(MODEL, device_map="cuda:0", dtype=torch.bfloat16)
    prompts = {}

    def get_prompt(name=None):
        """Prompt de clonación de un perfil (el del arranque si name es None); se crean al primer uso."""
        folder = profile if name is None else profile.parent / cast.get(name, {}).get("perfil", name)
        if folder not in prompts:
            prompts[folder] = model.create_voice_clone_prompt(
                ref_audio=str(folder / "ref.wav"), ref_text=(folder / "ref.txt").read_text().strip())
        return prompts[folder]

    get_prompt()
    print("listo", file=sys.stderr, flush=True)

    def generate_same(texts, voices, params):
        """Genera un lote con los mismos parámetros; si no cabe en la GPU, lo parte en dos y reintenta."""
        try:
            wavs, sr = model.generate_voice_clone(
                text=texts, language=[LANGUAGE] * len(texts),
                voice_clone_prompt=[item for v in voices for item in get_prompt(v)],
                max_new_tokens=max(256, TOKENS_PER_CHAR * max(len(t) for t in texts)), **params)
            return list(wavs), sr
        except torch.OutOfMemoryError:
            if len(texts) == 1:
                raise
        # Reintentar FUERA del except: dentro, la traza del error mantiene viva la memoria del intento fallido
        gc.collect()
        torch.cuda.empty_cache()
        half = len(texts) // 2
        print(f"lote de {len(texts)} sin memoria; lo parto en dos", file=sys.stderr, flush=True)
        w1, sr = generate_same(texts[:half], voices[:half], params)
        w2, _ = generate_same(texts[half:], voices[half:], params)
        return w1 + w2, sr

    def generate(texts, extra=None, voices=None):
        """Genera cada voz con su propio muestreo (+ extra, solo para esta petición: reintentos)."""
        voices = voices or [None] * len(texts)
        groups = {}
        for i, v in enumerate(voices):
            params = {**gen_for(v), **(extra or {})}
            if "temperature" in (extra or {}):
                params["subtalker_temperature"] = params["temperature"]
            groups.setdefault(json.dumps(params, sort_keys=True), []).append(i)
        wavs, sr = [None] * len(texts), None
        for key, idx in groups.items():
            ws, sr = generate_same([texts[i] for i in idx], [voices[i] for i in idx], json.loads(key))
            for i, w in zip(idx, ws):
                wavs[i] = w
        return wavs, sr

    out = _AUDIO_OUT
    for line in sys.stdin:
        if not line.strip():
            continue
        req = json.loads(line)
        texts = req["texts"]
        wavs, sr = generate(texts, req.get("gen"), req.get("voices"))
        for w, key in zip(wavs, req.get("voices") or [None] * len(wavs)):
            w = np.asarray(w, dtype=np.float32)
            if trim:
                w = trim_silence(w, sr)
            pcm = (np.clip(w, -1.0, 1.0) * 32767).astype("<i2").tobytes()
            pcm = atempo(pcm, sr, speed * cast.get(key, {}).get("velocidad", 1.0))
            out.write(struct.pack("<Q", len(pcm)) + pcm)
        out.flush()


if __name__ == "__main__":
    main()
