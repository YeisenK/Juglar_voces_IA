"""Recorta ref.wav de los perfiles de Qwen a ~6-11 s terminando en fin de frase (con Whisper).

Uso: recortar_referencias.py [voz ...]   (sin argumentos, todas)
"""
import json, os, subprocess, sys
import nvidia.cublas, nvidia.cudnn
for mod in (nvidia.cublas, nvidia.cudnn):
    os.environ["LD_LIBRARY_PATH"] = os.path.join(list(mod.__path__)[0], "lib") + ":" + os.environ.get("LD_LIBRARY_PATH", "")
if "REEXEC" not in os.environ:
    os.environ["REEXEC"] = "1"; os.execv(sys.executable, [sys.executable] + sys.argv)
from pathlib import Path
import numpy as np, soundfile as sf
from faster_whisper import WhisperModel
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "juglar"))
import rutas  # noqa: E402
V = rutas.VOCES
m = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
solo = set(sys.argv[1:])  # opcional: recortar solo estas voces
for d in sorted(x for x in V.iterdir() if x.is_dir() and (not solo or x.name in solo)):
    full = d/"ref_completo.wav"
    if not full.exists():
        (d/"ref.wav").rename(full); (d/"ref.txt").rename(d/"ref_completo.txt")
    audio, sr = sf.read(full, dtype="float32")
    a16 = np.frombuffer(subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(full), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                                       capture_output=True, check=True).stdout, np.float32)
    segs, _ = m.transcribe(a16, language="es", word_timestamps=True)
    words = [w for s in segs for w in s.words]
    # cortar en el primer final de frase entre 6 y 11 s; si no hay, en el último antes de 11 s
    cut, text = None, ""
    for i, w in enumerate(words):
        if w.word.strip()[-1:] in ".!?" and w.end <= 11.5:
            cut, text = w.end, "".join(x.word for x in words[:i+1]).strip()
            if w.end >= 6: break
    if cut is None:
        sys.exit(f"{d.name}: no encontré un final de frase antes de 11 s")
    end = min(len(audio), int((cut + 0.25) * sr))
    sf.write(d/"ref.wav", audio[:end], sr)
    (d/"ref.txt").write_text(text)
    print(f"{d.name}: {end/sr:.1f}s · «{text}»")
