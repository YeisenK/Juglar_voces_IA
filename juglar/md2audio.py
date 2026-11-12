#!/usr/bin/env python3
"""md2audio: convierte un archivo Markdown (o texto) en audio con Qwen3-TTS, Kokoro o Piper.

Pensado para archivos grandes: procesa por fragmentos en paralelo, codifica en
streaming con ffmpeg (memoria constante) y añade capítulos por cada encabezado.

Voces: qwen:PERFIL (qwen:narradora), kokoro:NOMBRE (kokoro:ef_dora) o nombre de Piper (es_ES-davefx-medium).

Uso: md2audio.py ENTRADA.md [-o SALIDA.mp3] [-v VOZ] [-s VELOCIDAD] [-j HILOS] [--json]
     md2audio.py - --raw -v VOZ < texto.txt | aplay ...   (PCM s16le mono en streaming)
     md2audio.py --list-voices                           (VOZ<TAB>frecuencia)
"""
import argparse
import contextlib
import html
import json
import multiprocessing as mp
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # con python -I el directorio del script no entra solo
import rutas  # noqa: E402
import texto_es  # noqa: E402
VENV_PY = rutas.VENV_PY
VOICES_DIR = rutas.PIPER_VOCES
KOKORO_DIR = rutas.KOKORO_DIR
KOKORO_MODEL = KOKORO_DIR / "kokoro-v1.0.onnx"
KOKORO_VOICES = KOKORO_DIR / "voices-v1.0.bin"
KOKORO_RATE = 24000
KOKORO_LANGS = {"e": "es", "a": "en-us", "b": "en-gb", "f": "fr-fr", "i": "it", "p": "pt-br", "h": "hi"}
QWEN_PY = rutas.QWEN_PY
QWEN_WORKER = rutas.MOTORES / "qwen_worker.py"
QWEN_VOICES = rutas.VOCES
LIBRO_FILE = QWEN_VOICES / "libro.json"
ELENCO = QWEN_VOICES / "elenco.json"      # personajes con nombre: {slug: {nombre, voz, temperature…, velocidad}}
QWEN_RATE = 24000
QWEN_BATCH = 8  # frases por lote en la GPU: ~6x tiempo real frente a ~1x de una en una
QWEN_BATCH_CHARS = int(os.environ.get("MD2AUDIO_QWEN_CHARS", 700))  # la memoria crece con lote × longitud; 8 frases de ~80 caracteres caben en 8 GB
# Ajustes de lectura de Qwen (se pueden cambiar por voz en <JUGLAR_DATA>/voces/<voz>/ajustes.json o con --qwen-ajustes)
QWEN_DEFAULTS = {
    "temperature": 0.9, "top_p": 1.0, "top_k": 50, "repetition_penalty": 1.05,  # muestreo del modelo
    "pausa_frase": 0.4,           # s entre fragmentos del mismo párrafo
    "pausa_parrafo": 0.4,         # s al terminar un párrafo
    "pausa_titulo_antes": 0.6, "pausa_titulo_despues": 0.5,
    "pausa_escena": 2.0,          # s en un cambio de escena (--- o ***)
    "fragmento": 250,             # caracteres máx. por fragmento
    "voz_dialogo": None,          # perfil de Qwen que lee los diálogos (rayas); None = la misma voz
    "pausa_voz": 0.2,             # s al cambiar entre narrador y personaje dentro de un párrafo
    "revisar": True,              # comprobar con Whisper cada fragmento y regenerar los que salgan mal
    "revision_umbral": 0.2,       # fracción de palabras distintas a partir de la cual se regenera
    "revision_min_errores": 3,    # ...y siempre que sean al menos tantas palabras (un nombre inventado no cuenta)
    "recortar_silencios": True,   # quita el silencio que deja el modelo; las pausas son las de arriba
    "nivelar": True,              # igualar el volumen de los fragmentos al guardar
    "normalizar_texto": True,     # pasar números, fechas, abreviaturas… a palabras
    "flash": False,               # modo flash: sin revisar con Whisper y todo con la voz del narrador
}
VOICE_KEYS = ("temperature", "top_p", "top_k", "repetition_penalty")   # lo que se ajusta voz a voz
WHISPER_PY = rutas.WHISPER_PY
WHISPER_WORKER = rutas.MOTORES / "whisper_worker.py"
REVISION_LOG = rutas.CACHE / "revision.log"
QWEN_LOG = rutas.CACHE / "qwen.log"

# Relanzar con el Python del entorno de Piper si se ejecuta con otro intérprete
if __name__ == "__main__" and Path(sys.prefix).resolve() != VENV_PY.parent.parent.resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), "-I", os.path.abspath(__file__), *sys.argv[1:]])
DEFAULT_VOICE = "qwen:narradora" if (QWEN_VOICES / "narradora").is_dir() else "es_ES-davefx-medium"
MAX_CHUNK = 1500  # caracteres por fragmento de síntesis

# ---------------------------------------------------------------- Markdown -> texto

RE_FENCE = re.compile(r"^\s*(```|~~~)")
RE_ATX = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
RE_SETEXT = re.compile(r"^\s{0,3}(=+|-+)\s*$")
RE_HR = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
RE_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?")
RE_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
RE_REFDEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s+\S+")


def clean_inline(s: str) -> str:
    s = re.sub(r"<!--.*?-->", " ", s)
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)          # imágenes -> texto alternativo
    s = re.sub(r"!\[([^\]]*)\]\[[^\]]*\]", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)           # [texto](url)
    s = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", s)          # [texto][ref]
    s = re.sub(r"\[\^[^\]]+\]", "", s)                        # notas al pie
    s = re.sub(r"<(https?://|mailto:)[^>]+>", "", s)          # autolinks
    s = re.sub(r"https?://\S+", "", s)                        # URLs sueltas
    s = re.sub(r"</?[A-Za-z][^>]*>", " ", s)                  # etiquetas HTML
    s = re.sub(r"`+([^`]*)`+", r"\1", s)                      # código en línea
    s = re.sub(r"(\*\*|__)(.+?)\1", r"\2", s)                 # negrita
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", s)  # cursiva *
    s = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", s)          # cursiva _
    s = re.sub(r"~~(.+?)~~", r"\1", s)
    s = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>~])", r"\1", s)     # escapes
    s = html.unescape(s)
    s = s.replace("|", ", ")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+,", ",", s).strip(" ,")
    return s


def end_punct(s: str) -> str:
    return s if not s or s[-1] in ".!?…:;¡¿" else s + "."


def md_to_segments(md: str):
    """Devuelve una lista de (tipo, texto); tipo es 'h' (encabezado) o 'p' (párrafo)."""
    md = md.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    md = re.sub(r"\A---\n.*?\n(---|\.\.\.)\n", "", md, flags=re.S)  # front matter YAML
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)

    segs, para = [], []
    in_fence, fence = False, ""

    def flush():
        if para:
            text = clean_inline(" ".join(para))
            if text:
                segs.append(("p", end_punct(text)))
            para.clear()

    lines = md.split("\n")
    for i, line in enumerate(lines):
        m = RE_FENCE.match(line)
        if in_fence:
            if m and m.group(1) == fence:
                in_fence = False
            continue
        if m:
            flush()
            in_fence, fence = True, m.group(1)
            continue
        if not line.strip():
            flush()
            continue
        if RE_REFDEF.match(line):
            continue
        m = RE_ATX.match(line)
        if m:
            flush()
            t = clean_inline(m.group(2))
            if t:
                segs.append(("h", end_punct(t)))
            continue
        if RE_SETEXT.match(line) and para and not RE_LIST.match(para[-1]):
            title = para.pop()
            flush()
            t = clean_inline(title)
            if t:
                segs.append(("h", end_punct(t)))
            continue
        if RE_HR.match(line):
            flush()
            if segs and segs[-1][0] != "b":
                segs.append(("b", ""))  # cambio de escena: solo una pausa larga
            continue
        if RE_TABLE_SEP.match(line):
            continue
        stripped = re.sub(r"^\s*(>\s?)+", "", line)          # citas
        if RE_LIST.match(stripped):
            flush()
            para.append(RE_LIST.sub("", stripped))
            flush()  # cada elemento de lista como frase propia
            continue
        if stripped.strip().startswith("|"):
            flush()
            para.append(stripped)
            flush()
            continue
        para.append(stripped.strip())
    flush()
    return segs


def split_long(text: str, limit: int = MAX_CHUNK):
    """Parte párrafos enormes por frases para repartir mejor el trabajo."""
    if len(text) <= limit:
        return [text]
    out, cur = [], ""
    for sent in re.split(r"(?<=[.!?…;:])\s+", text):
        if cur and len(cur) + len(sent) + 1 > limit:
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------- voces

OBJETIVO_DB = -18.0   # nivel (RMS de las partes con voz) al que se iguala cada fragmento: ~ -19 LUFS, habitual en audiolibros
PAUSA_ESCENA = 1.5    # s en un cambio de escena con las voces que no son de Qwen


def nivelar(pcm: bytes, rate: int, objetivo_db=OBJETIVO_DB, max_db=8.0):
    """Iguala el volumen del fragmento al nivel objetivo (sin pasar de ±max_db ni recortar)."""
    import numpy as np
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
    paso = int(rate * 0.02)
    n = len(x) // paso * paso
    if n == 0:
        return pcm
    rms = np.sqrt((x[:n].reshape(-1, paso) ** 2).mean(axis=1))
    voz = rms[rms > 10 ** (-45 / 20)]
    if voz.size == 0:
        return pcm
    nivel = float(np.sqrt((voz ** 2).mean()))
    ganancia = float(np.clip(objetivo_db - 20 * np.log10(nivel), -max_db, max_db))
    y = x * 10 ** (ganancia / 20)
    pico = float(np.abs(y).max())
    if pico > 0.97:
        y *= 0.97 / pico
    return (y * 32767).astype("<i2").tobytes()


def _json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def libro_settings():
    """Ajustes comunes a todas las voces y motores: valores de fábrica + libro.json."""
    return {**QWEN_DEFAULTS, **_json(LIBRO_FILE)}


def qwen_settings(profile, override=None):
    """Ajustes de lectura de una voz de Qwen: fábrica + libro.json (comunes) + ajustes.json de la voz + override."""
    return {**libro_settings(), **_json(QWEN_VOICES / profile / "ajustes.json"), **(override or {})}


PERSONAJES = QWEN_VOICES / "personajes.json"
MARCAS_VALIDAS = set(range(1, 10))   # —1 … —9 al empezar una intervención


def personajes():
    """{número: perfil} de las voces de los personajes (—1, —2…). Sin personajes.json, las voces por orden."""
    perfiles = qwen_profiles()
    guardado = _json(PERSONAJES)
    if guardado:
        return {int(k): v for k, v in guardado.items() if v in perfiles}
    return {i + 1: n for i, n in enumerate(perfiles[:5])}


def elenco():
    """{slug: ficha} de los personajes con nombre cuya voz base existe."""
    perfiles = qwen_profiles()
    return {k: f for k, f in _json(ELENCO).items() if f.get("voz") in perfiles}


def marcas_voces():
    """{marca: perfil} para escribir —@marca con una voz de Qwen: su carpeta, su nombre visible y ese nombre sin
    el paréntesis si le quedan al menos dos palabras («Vieja de pueblo (brava)» → vieja_brava, vieja_de_pueblo_brava y vieja_de_pueblo).
    Un alias que coincide con otra voz o con un personaje, o que comparten dos voces, no se usa."""
    perfiles, personajes_ = qwen_profiles(), set(_json(ELENCO))
    marcas, repetidas = {p: p for p in perfiles}, set()
    for p in perfiles:
        label = _json(QWEN_VOICES / p / "meta.json").get("label", "")
        corto = texto_es.slug(re.sub(r"\(.*?\)", "", label))
        for alias in {texto_es.slug(label), corto if "_" in corto else ""} - {"", p}:  # «mujer» a secas, no
            if alias in perfiles or alias in personajes_:
                continue
            if alias in marcas and marcas[alias] != p:
                repetidas.add(alias)
            marcas[alias] = p
    return {k: v for k, v in marcas.items() if k not in repetidas}


def ficha_ajustes(ficha, override=None):
    """Ajustes de lectura de un personaje: los de su voz base con sus propios cambios encima."""
    base = qwen_settings(ficha["voz"], override)
    return {**base, **{k: ficha[k] for k in VOICE_KEYS if k in ficha}}


def qwen_override(a):
    """Ajustes de esta ejecución (--qwen-ajustes y --voz-dialogo), que mandan sobre los guardados."""
    override = json.loads(a.qwen_ajustes) if a.qwen_ajustes else {}
    if a.voz_dialogo:
        override["voz_dialogo"] = a.voz_dialogo.split(":", 1)[-1]
    return override


def qwen_cfg(a):
    """Ajustes de Qwen para esta ejecución (voz elegida + --qwen-ajustes + --voz-dialogo)."""
    return qwen_settings(a.voice.split(":", 1)[1], qwen_override(a))


def qwen_profiles():
    """Perfiles de voz de Qwen (carpetas con ref.wav + ref.txt), la narradora primero."""
    if not QWEN_PY.exists() or not QWEN_VOICES.is_dir():
        return []
    names = sorted(d.name for d in QWEN_VOICES.iterdir() if (d / "ref.wav").exists() and (d / "ref.txt").exists())
    order = ["narradora", "narrador", "narradora_espana", "documental_mujer", "documental_hombre"]
    return sorted(names, key=lambda n: (order.index(n) if n in order else len(order), n))


def list_voices(all_kokoro=False):
    """Voces instaladas: Qwen (mejor calidad), Kokoro (solo español salvo all_kokoro) y Piper."""
    voices = [f"qwen:{n}" for n in qwen_profiles()]
    voices += sorted(p.stem for p in VOICES_DIR.glob("*.onnx"))
    if KOKORO_MODEL.exists() and KOKORO_VOICES.exists():
        import numpy as np
        names = sorted(np.load(KOKORO_VOICES).keys())
        voices += [f"kokoro:{n}" for n in names if all_kokoro or n[:1] == "e"]
    return voices


def voice_rate(spec):
    if spec.startswith("qwen:"):
        return QWEN_RATE
    if spec.startswith("kokoro:"):
        return KOKORO_RATE
    return json.loads((VOICES_DIR / f"{spec}.onnx.json").read_text())["audio"]["sample_rate"]


def voice_exists(spec):
    if spec.startswith("qwen:"):
        return spec.split(":", 1)[1] in qwen_profiles()
    if spec.startswith("kokoro:"):
        return KOKORO_MODEL.exists() and KOKORO_VOICES.exists()
    return (VOICES_DIR / f"{spec}.onnx").exists()


# ---------------------------------------------------------------- Qwen3-TTS

class QwenEngine:
    """Habla con qwen_worker.py, que corre en el entorno de Qwen y mantiene el modelo cargado en la GPU."""

    def __init__(self, profile, speed, settings=None, override=None):
        import ctypes
        import struct  # noqa: F401  (usado en synth)

        libc = ctypes.CDLL(None)
        QWEN_LOG.parent.mkdir(parents=True, exist_ok=True)
        self.log = open(QWEN_LOG, "wb")
        self.proc = subprocess.Popen(
            [str(QWEN_PY), str(QWEN_WORKER), str(QWEN_VOICES / profile), f"{speed:.3f}",
             json.dumps({**(settings or qwen_settings(profile, override)),
                        # muestreo propio de cada voz (la de los personajes puede tener otra temperatura)
                        "voces": {n: {k: qwen_settings(n, override)[k] for k in VOICE_KEYS}
                                  for n in qwen_profiles()},
                        # personajes con nombre: clave «@slug» = voz base + muestreo y velocidad propios
                        "personajes": {"@" + k: {"perfil": f["voz"], "velocidad": f.get("velocidad", 1.0),
                                                 **{x: ficha_ajustes(f, override)[x] for x in VOICE_KEYS}}
                                       for k, f in elenco().items()}})],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
            preexec_fn=lambda: libc.prctl(1, signal.SIGTERM))  # muere si md2audio muere

    def synth(self, texts, gen=None, voices=None):
        import struct

        try:
            req = {"texts": texts, **({"gen": gen} if gen else {}), **({"voices": voices} if voices else {})}
            self.proc.stdin.write((json.dumps(req, ensure_ascii=False) + "\n").encode())
            self.proc.stdin.flush()
            out = []
            for _ in texts:
                head = self.proc.stdout.read(8)
                if len(head) < 8:
                    raise EOFError
                out.append(self.proc.stdout.read(struct.unpack("<Q", head)[0]))
            return out
        except (EOFError, BrokenPipeError):
            self.proc.wait()
            tail = QWEN_LOG.read_text(errors="replace").strip().splitlines()[-3:]
            msg = " ".join(tail)
            if "OutOfMemory" in msg or "out of memory" in msg:
                msg = "La GPU no tiene memoria libre para Qwen (¿otra app usando la tarjeta?)"
            raise RuntimeError(f"Qwen falló: {msg[-300:]}") from None

    def close(self):
        with contextlib.suppress(Exception):
            self.proc.stdin.close()
            self.proc.wait(timeout=10)


def qwen_batches(texts, voices=None, first=QWEN_BATCH):
    """Agrupa los textos en lotes (textos, voces) para la GPU; el primero puede ser más pequeño."""
    voices = voices or [None] * len(texts)
    i, limit = 0, first
    while i < len(texts):
        j, chars = i, 0
        while j < len(texts) and j - i < limit and (j == i or chars + len(texts[j]) <= QWEN_BATCH_CHARS):
            chars += len(texts[j])
            j += 1
        yield texts[i:j], voices[i:j]
        i, limit = j, QWEN_BATCH


def qwen_results(engine, texts, voices=None, first=QWEN_BATCH):
    """Genera en lotes y devuelve el audio en orden."""
    for batch, bvoices in qwen_batches(texts, voices, first):
        yield from engine.synth(batch, voices=bvoices)


# ---------------------------------------------------------------- revisión con Whisper

def _palabras(t):
    import unicodedata
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")  # sin tildes: Whisper no siempre las pone
    return re.sub(r"[^\w\s]|_", " ", t).split()


def comparar(esperado, oido):
    """(palabras distintas, fracción) entre el texto que debía decir la voz y lo que Whisper oyó."""
    ref = _palabras(esperado)
    hyp = _palabras(texto_es.normalizar(oido, diccionario=False))  # «32» -> «treinta y dos», como el texto leído
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
    return d[len(hyp)], d[len(hyp)] / max(len(ref), 1)


class Revisor:
    """Transcribe el audio generado con whisper_worker.py (CPU, en paralelo a la GPU)."""

    def __init__(self, rate):
        import queue
        import threading
        self.rate, self.next_id, self.results = rate, 0, {}
        self.cond, self.alive, self.q = threading.Condition(), True, queue.Queue()
        import ctypes
        libc = ctypes.CDLL(None)
        REVISION_LOG.parent.mkdir(parents=True, exist_ok=True)
        self.log = open(REVISION_LOG, "ab")
        self.proc = subprocess.Popen(
            [str(WHISPER_PY), "-I", str(WHISPER_WORKER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.log, preexec_fn=lambda: libc.prctl(1, signal.SIGTERM))
        threading.Thread(target=self._write, daemon=True).start()
        threading.Thread(target=self._read, daemon=True).start()

    def _write(self):
        try:
            while True:
                item = self.q.get()
                if item is None:
                    break
                n, pcm = item
                self.proc.stdin.write((json.dumps({"id": n, "rate": self.rate, "bytes": len(pcm)}) + "\n").encode())
                self.proc.stdin.write(pcm)
                self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass

    def _read(self):
        for line in self.proc.stdout:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            with self.cond:
                self.results[r["id"]] = r.get("text")
                self.cond.notify_all()
        with self.cond:  # el proceso terminó: nadie más va a contestar
            self.alive = False
            self.cond.notify_all()

    def submit(self, pcm):
        self.next_id += 1
        self.q.put((self.next_id, pcm))
        return self.next_id

    def result(self, n):
        """Texto oído, o None si Whisper no pudo (la revisión se da por buena)."""
        with self.cond:
            while n not in self.results and self.alive:
                self.cond.wait(1.0)
            return self.results.pop(n, None)

    def close(self):
        self.q.put(None)
        with contextlib.suppress(Exception):
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        with contextlib.suppress(Exception):
            self.proc.kill()


def qwen_revisados(engine, rev, texts, voices, cfg, stats, first=QWEN_BATCH):
    """Como qwen_results, pero comprueba cada fragmento con Whisper y regenera los que no dicen lo que deben.

    Mientras la GPU genera el lote siguiente, la CPU revisa el anterior. Cada fragmento dudoso se vuelve a
    generar hasta 2 veces (la 2.ª con menos aleatoriedad) y se queda con el mejor intento.
    """
    umbral = cfg["revision_umbral"]
    reintentos = [None, {"temperature": 0.7}]

    def mal(texto, pcm, oido):
        if oido is None:
            return 0.0, False
        n, frac = comparar(texto, oido)
        seg = len(pcm) / 2 / QWEN_RATE
        raro = len(texto) >= 25 and seg > 0 and not 5 <= len(texto) / seg <= 32  # caracteres por segundo fuera de lo humano
        return frac, (n >= cfg["revision_min_errores"] and frac > umbral) or raro

    def revisar(lote, voces, pcms, ids):
        for texto, voz, pcm, n in zip(lote, voces, pcms, ids):
            frac, falla = mal(texto, pcm, rev.result(n))
            stats["revisados"] += 1
            mejor, mejor_frac = pcm, frac
            if falla:
                stats["dudosos"] += 1
                for extra in reintentos:
                    nuevo = engine.synth([texto], extra, [voz])[0]
                    f2, falla2 = mal(texto, nuevo, rev.result(rev.submit(nuevo)))
                    stats["regenerados"] += 1
                    if f2 < mejor_frac:
                        mejor, mejor_frac = nuevo, f2
                    if not falla2:
                        break
                if mejor_frac > umbral:
                    stats["sin_arreglar"] += 1
                    with contextlib.suppress(OSError):
                        REVISION_LOG.open("a").write(f"sin arreglar ({mejor_frac:.0%}): {texto}\n")
                else:
                    stats["arreglados"] += 1
            yield mejor

    anterior = None
    for lote, voces in qwen_batches(texts, voices, first):
        pcms = engine.synth(lote, voices=voces)
        ids = [rev.submit(p) for p in pcms]
        if anterior:
            yield from revisar(*anterior)
        anterior = (lote, voces, pcms, ids)
    if anterior:
        yield from revisar(*anterior)


# ---------------------------------------------------------------- síntesis en paralelo

_voice = None
_syn = None


_init_error = None


def _init_worker(*args):
    # Si el inicializador lanza, Pool reintenta sin fin; se guarda el error y se lanza en _synth
    global _init_error
    try:
        _load_voice(*args)
    except Exception as e:  # noqa: BLE001
        _init_error = e


def gpu_available():
    """True si onnxruntime puede usar CUDA (onnxruntime-gpu + librerías nvidia de pip)."""
    try:
        import onnxruntime

        if "CUDAExecutionProvider" not in onnxruntime.get_available_providers():
            return False
        onnxruntime.preload_dlls()
        return True
    except Exception:  # noqa: BLE001
        return False


device = "CPU"  # dónde se está sintetizando realmente; puede pasar de GPU a CPU a mitad


def _kokoro_session(threads, gpu):
    """Sesión de Kokoro en la GPU si se pide y cabe; si no (p. ej. otra app llenó la VRAM), en CPU."""
    global device
    import onnxruntime

    opts = onnxruntime.SessionOptions()
    opts.log_severity_level = 3
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = 1
    if gpu:
        try:
            sess = onnxruntime.InferenceSession(str(KOKORO_MODEL), sess_options=opts, providers=[
                ("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC",
                                           "arena_extend_strategy": "kSameAsRequested"})])
            device = "GPU"
            return sess
        except Exception as e:  # noqa: BLE001
            print(f"GPU no disponible ({str(e).splitlines()[0][:160]}); usando CPU", file=sys.stderr)
    device = "CPU"
    return onnxruntime.InferenceSession(str(KOKORO_MODEL), sess_options=opts,
                                        providers=["CPUExecutionProvider"])


def _load_voice(spec, speed, threads, gpu=False):
    global _voice, _syn
    import onnxruntime

    onnxruntime.set_default_logger_severity(3)  # sin avisos de rendimiento por stderr
    opts = onnxruntime.SessionOptions()
    opts.log_severity_level = 3
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = 1
    if spec.startswith("kokoro:"):
        from kokoro_onnx import Kokoro

        name = spec.split(":", 1)[1]
        _voice = Kokoro.from_session(_kokoro_session(threads, gpu), str(KOKORO_VOICES))
        _syn = ("kokoro", name, speed, KOKORO_LANGS.get(name[:1], "es"), threads)
    else:
        from piper import PiperVoice, SynthesisConfig
        from piper.config import PiperConfig
        from piper.voice import ESPEAK_DATA_DIR

        # Igual que PiperVoice.load pero con nuestras opciones de hilos (sin cargar el modelo dos veces)
        model = VOICES_DIR / f"{spec}.onnx"
        _voice = PiperVoice(
            config=PiperConfig.from_dict(json.loads(Path(f"{model}.json").read_text(encoding="utf-8"))),
            session=onnxruntime.InferenceSession(str(model), sess_options=opts,
                                                 providers=["CPUExecutionProvider"]),
            espeak_data_dir=Path(ESPEAK_DATA_DIR), download_dir=Path.cwd())
        _syn = SynthesisConfig(length_scale=1.0 / speed)  # length_scale: mayor = más lento


def _synth(text):
    if _init_error:
        raise RuntimeError(f"No se pudo cargar la voz: {_init_error}")
    if isinstance(_syn, tuple):
        import numpy as np

        global _voice
        _, name, speed, lang, threads = _syn
        try:
            audio, _sr = _voice.create(text, voice=name, speed=speed, lang=lang)
        except Exception as e:  # noqa: BLE001
            if device != "GPU":
                raise
            # la VRAM se llenó a mitad (otra app cargó un modelo): seguir en CPU sin perder lo hecho
            print(f"Fallo en la GPU ({str(e).splitlines()[0][:160]}); sigo en CPU", file=sys.stderr)
            from kokoro_onnx import Kokoro

            _voice = Kokoro.from_session(_kokoro_session(threads, False), str(KOKORO_VOICES))
            audio, _sr = _voice.create(text, voice=name, speed=speed, lang=lang)
        return (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    return b"".join(c.audio_int16_bytes for c in _voice.synthesize(text, syn_config=_syn))


# ---------------------------------------------------------------- principal

def emit(as_json, **kw):
    if as_json:
        print(json.dumps(kw, ensure_ascii=False), flush=True)
    elif kw["type"] == "progress":
        pct = 100 * kw["done"] / max(kw["total"], 1)
        eta = kw.get("eta")
        eta_s = f" · quedan ~{int(eta // 60)}:{int(eta % 60):02d}" if eta is not None else ""
        print(f"\r{pct:5.1f}%{eta_s}   ", end="", file=sys.stderr, flush=True)
    elif kw["type"] == "done":
        print(f"\nListo: {kw['output']} ({kw['duration']/60:.1f} min de audio)", file=sys.stderr)
    elif kw["type"] in ("error", "info"):
        print(("\nError: " if kw["type"] == "error" else "") + kw["message"], file=sys.stderr)


def fmt_codec(path: Path):
    ext = path.suffix.lower()
    if ext == ".mp3":
        return ["-c:a", "libmp3lame", "-q:a", "5"]
    if ext in (".ogg", ".opus"):
        return ["-c:a", "libopus", "-b:a", "32k", "-application", "voip"]
    if ext in (".m4a", ".m4b"):
        return ["-c:a", "aac", "-b:a", "64k"]
    if ext == ".wav":
        return ["-c:a", "pcm_s16le"]
    raise SystemExit(f"Formato no soportado: {ext} (usa .mp3, .ogg, .opus, .m4a, .m4b o .wav)")


def main():
    ap = argparse.ArgumentParser(description="Convierte Markdown/texto a audio con Piper")
    ap.add_argument("input", nargs="?", help="archivo .md/.txt, o - para leer de stdin")
    ap.add_argument("-o", "--output", help="archivo de salida (por defecto ENTRADA.mp3)")
    ap.add_argument("-v", "--voice", default=os.environ.get("PIPER_VOICE", DEFAULT_VOICE))
    ap.add_argument("-s", "--speed", type=float, default=1.0, help="velocidad (1.0 normal, 1.2 más rápido)")
    ap.add_argument("-j", "--jobs", type=int, default=0, help="procesos en paralelo (0 = auto)")
    ap.add_argument("--json", action="store_true", help="progreso en JSON por stdout (para la app)")
    ap.add_argument("--text-only", action="store_true", help="solo muestra el texto limpio que se leería")
    ap.add_argument("--raw", action="store_true", help="escribe PCM s16le mono por stdout (para reproducir)")
    ap.add_argument("--list-voices", action="store_true", help="lista las voces instaladas y su frecuencia")
    ap.add_argument("--qwen-ajustes", metavar="JSON", help="ajustes de Qwen para esta ejecución, p. ej. '{\"temperature\": 0.7}'")
    ap.add_argument("--literal", action="store_true", help="leer el texto tal cual, sin pasar números, fechas, abreviaturas, etc. a palabras")
    ap.add_argument("--sin-nivelar", action="store_true", help="no igualar el volumen de los fragmentos")
    ap.add_argument("--no-revisar", action="store_true", help="con Qwen: no comprobar el audio con Whisper")
    ap.add_argument("--flash", action="store_true",
                    help="con Qwen: modo rápido, sin revisar con Whisper y todo con la voz del narrador")
    ap.add_argument("--sin-flash", action="store_true", help="ignorar el modo flash guardado en los ajustes")
    ap.add_argument("--voz-dialogo", metavar="VOZ", help="con Qwen: voz que lee los diálogos (rayas), p. ej. qwen:narradora")
    ap.add_argument("--cpu", action="store_true", help="no usar la GPU aunque esté disponible")
    ap.add_argument("--all-kokoro", action="store_true", help="con --list-voices: incluye voces de Kokoro de otros idiomas")
    a = ap.parse_args()

    if a.list_voices:
        for v in list_voices(a.all_kokoro):
            print(f"{v}\t{voice_rate(v)}")
        return
    if not a.input:
        ap.error("falta el archivo de entrada")

    if a.input == "-":
        src = Path("stdin.md")
        raw = sys.stdin.read()
    else:
        src = Path(a.input)
        raw = src.read_text(encoding="utf-8", errors="replace")
    segs = md_to_segments(raw) if src.suffix.lower() in (".md", ".markdown", ".mdx") else \
        [("p", end_punct(clean_inline(p))) for p in re.split(r"\n\s*\n", raw) if p.strip()]

    if a.text_only:
        for kind, t in segs:
            if kind == "b":
                print("\n[pausa de escena]\n")
                continue
            t = texto_es.quitar_marca(t, MARCAS_VALIDAS, set(elenco()))[0] if kind == "p" else t
            print(("\n## " if kind == "h" else "") + (t if a.literal or not libro_settings()["normalizar_texto"] else texto_es.normalizar(t)) + "\n")
        return

    if not segs:
        emit(a.json, type="error", message="El archivo no contiene texto legible")
        sys.exit(1)

    if not voice_exists(a.voice):
        emit(a.json, type="error", message=f"Voz no encontrada: {a.voice}")
        sys.exit(1)
    rate = voice_rate(a.voice)
    kokoro = a.voice.startswith("kokoro:")
    qwen = a.voice.startswith("qwen:")
    try:  # comprobar aquí; un fallo dentro del pool lo haría reintentar sin fin
        import onnxruntime  # noqa: F401
        if qwen:
            pass  # Qwen corre en su propio entorno (qwen_worker.py)
        elif kokoro:
            import kokoro_onnx  # noqa: F401
        else:
            import piper  # noqa: F401
    except ImportError as e:
        emit(a.json, type="error", message=f"Falta Piper en este Python: {e}")
        sys.exit(1)

    # En streaming se usan fragmentos cortos para que empiece a sonar enseguida
    # Qwen: fragmentos medianos, que en lote ocupan memoria parecida y no se desvían en textos largos
    qcfg = qwen_cfg(a) if qwen else None
    chunk_limit = 200 if a.raw else (qcfg["fragmento"] if qwen else MAX_CHUNK)
    # Modo flash: ni Whisper ni voces de personajes; las marcas (—2, —@leonor) se quitan y lo lee todo el narrador
    flash = qwen and not a.sin_flash and (a.flash or bool(qcfg["flash"]))

    # Trabajos: (texto, silencio_antes_seg, silencio_después_seg, título_capítulo)
    jobs = []
    escena = qcfg["pausa_escena"] if qwen else PAUSA_ESCENA
    voz_dialogo = qcfg["voz_dialogo"] if qwen and not flash and qcfg["voz_dialogo"] in qwen_profiles() else None
    propia = a.voice.split(":", 1)[-1]
    mapa_personajes = personajes() if qwen else {}
    nombres = elenco()
    # —@nombre también vale con el nombre de una voz (—@tabernero) aunque no sea un personaje; el personaje manda
    alias = marcas_voces() if qwen else {}
    marcables = set(nombres) | set(alias)
    libro = libro_settings()
    prep = (lambda t: t) if a.literal or not libro["normalizar_texto"] else texto_es.normalizar
    for kind, text in segs:
        if kind == "b":  # el silencio se suma al final del fragmento anterior
            if jobs:
                t, pre, post, ch, v = jobs[-1]
                jobs[-1] = (t, pre, max(post, escena), ch, v)
            continue
        # (voz, texto): los párrafos con rayas se reparten entre narrador y personajes (—1, —2… eligen la voz)
        piezas = [(None, prep(text))]  # el título del capítulo se queda como está escrito
        if kind == "p" and text.lstrip()[:1] in "—–":
            if qwen and not flash:
                trozos = texto_es.dividir_dialogo(text, validas=set(mapa_personajes), nombres=marcables)
                voces = [(((("@" + num) if num in nombres else alias[num]) if isinstance(num, str) else mapa_personajes.get(num))
                          if num else voz_dialogo)
                         if rol == "dialogo" else None for rol, _t, num in trozos]
                if any(v and v != propia for v in voces):  # solo se trocea si de verdad cambia la voz
                    piezas = [(v if v != propia else None, end_punct(prep(t))) for v, (_r, t, _n) in zip(voces, trozos)]
                else:
                    piezas = [(None, prep(texto_es.quitar_marca(text, set(mapa_personajes), marcables)[0]))]
            else:
                piezas = [(None, prep(texto_es.quitar_marca(text, set(mapa_personajes) if qwen else MARCAS_VALIDAS, marcables)[0]))]
        for n, (voz, spoken) in enumerate(piezas):
            parts = split_long(spoken, chunk_limit)
            for k, part in enumerate(parts):
                last = k == len(parts) - 1
                if qwen:
                    if kind == "h":
                        jobs.append((part, qcfg["pausa_titulo_antes"] if jobs and k == 0 else 0.0,
                                     qcfg["pausa_titulo_despues"] if last else qcfg["pausa_frase"],
                                     text if k == 0 else None, voz))
                    else:
                        fin = qcfg["pausa_parrafo"] if n == len(piezas) - 1 else qcfg["pausa_voz"]
                        jobs.append((part, 0.0, fin if last else qcfg["pausa_frase"], None, voz))
                elif kind == "h":
                    jobs.append((part, 0.6 if jobs else 0.0, 0.5, text if k == 0 else None, None))
                else:
                    jobs.append((part, 0.0, 0.4, None, None))
    for aviso in dict.fromkeys(texto_es.AVISOS):
        print(aviso, file=sys.stderr)
    total_chars = sum(len(j[0]) for j in jobs)

    ncpu = os.cpu_count() or 4
    # Kokoro va mucho más rápido en la GPU; Piper ya es muy rápido en CPU y CUDA solo retrasaría el arranque
    gpu = (kokoro and not a.cpu and gpu_available()) or qwen
    if gpu or a.raw:
        workers = 1  # un único proceso: la GPU no se reparte bien y en streaming prima arrancar rápido
    else:
        # Kokoro ocupa ~600 MB por proceso en CPU: menos procesos y más hilos cada uno
        workers = a.jobs or max(1, min(len(jobs), ncpu // 2, 4 if kokoro else 8))
    threads = max(1, ncpu // workers)

    if a.raw:
        return stream_raw(a, jobs, rate, threads, gpu)

    out = Path(a.output) if a.output else src.with_suffix(".mp3")
    codec = fmt_codec(out)

    def _on_term(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _on_term)  # cancelar desde la app limpia los temporales

    tmpdir = Path(tempfile.mkdtemp(prefix="md2audio-"))
    tmp_audio = tmpdir / ("audio" + out.suffix)
    enc = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "-", *codec, str(tmp_audio)],
        stdin=subprocess.PIPE)

    emit(a.json, type="start", total=total_chars, segments=len(jobs), workers=workers, output=str(out))
    silence = lambda sec: b"\x00\x00" * int(rate * sec)  # noqa: E731
    chapters, samples, done, t0 = [], 0, 0, time.time()
    t_first, done_first = None, 0
    revision = {"revisados": 0, "dudosos": 0, "regenerados": 0, "arreglados": 0, "sin_arreglar": 0}
    try:
        with contextlib.ExitStack() as stack:
            if qwen:
                engine = QwenEngine(a.voice.split(":", 1)[1], a.speed, qwen_cfg(a), qwen_override(a))
                stack.callback(engine.close)
                globals()["device"] = "GPU"  # Qwen siempre genera en la tarjeta gráfica
                qcfg_run = qwen_cfg(a)
                if qcfg_run["revisar"] and not a.no_revisar and not flash and WHISPER_PY.exists() and WHISPER_WORKER.exists():
                    rev = Revisor(rate)
                    stack.callback(rev.close)
                    results = qwen_revisados(engine, rev, [j[0] for j in jobs], [j[4] for j in jobs], qcfg_run, revision)
                else:
                    results = qwen_results(engine, [j[0] for j in jobs], [j[4] for j in jobs])
            elif workers == 1:  # en el propio proceso (GPU)
                _load_voice(a.voice, a.speed, threads, gpu)
                results = map(_synth, (j[0] for j in jobs))
            else:
                pool = stack.enter_context(mp.get_context("spawn").Pool(
                    workers, initializer=_init_worker, initargs=(a.voice, a.speed, threads)))
                results = pool.imap(_synth, (j[0] for j in jobs))
            for (text, pre, post, title, _voz), pcm in zip(jobs, results):
                if title:
                    chapters.append((samples + int(rate * pre), title))
                if not a.sin_nivelar and libro["nivelar"]:
                    pcm = nivelar(pcm, rate)
                chunk = silence(pre) + pcm + silence(post)
                enc.stdin.write(chunk)
                samples += len(chunk) // 2
                done += len(text)
                now = time.time()
                if t_first is None:  # la carga de las voces no cuenta para el ritmo
                    t_first, done_first = now, done
                rate_cps = (done - done_first) / (now - t_first) if now > t_first and done > done_first else 0
                emit(a.json, type="progress", done=done, total=total_chars, elapsed=now - t0, device=device,
                     eta=(total_chars - done) / rate_cps if rate_cps and done - done_first > total_chars * 0.02 else None)
        enc.stdin.close()
        if enc.wait() != 0:
            raise RuntimeError("ffmpeg falló al codificar")

        # Añadir capítulos (encabezados) sin recodificar
        if chapters and out.suffix.lower() != ".wav":
            meta = tmpdir / "meta.txt"
            lines = [";FFMETADATA1", f"title={src.stem}"]
            bounds = [c[0] for c in chapters[1:]] + [samples]
            for (start, title), end in zip(chapters, bounds):
                t = re.sub(r"([=;#\\\n])", r"\\\1", title.rstrip("."))
                lines += ["[CHAPTER]", f"TIMEBASE=1/{rate}", f"START={start}", f"END={end}", f"title={t}"]
            meta.write_text("\n".join(lines) + "\n", encoding="utf-8")
            final = tmpdir / ("final" + out.suffix)
            r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(tmp_audio),
                                "-i", str(meta), "-map", "0", "-map_metadata", "1", "-map_chapters", "1",
                                "-c", "copy", str(final)])
            if r.returncode == 0:
                tmp_audio = final
        shutil.move(str(tmp_audio), out)
        emit(a.json, type="done", output=str(out), duration=samples / rate, chapters=len(chapters),
             revision=revision if revision["revisados"] else None)
    except (KeyboardInterrupt, BrokenPipeError):
        enc.kill()
        emit(a.json, type="error", message="Cancelado")
        sys.exit(130)
    except Exception as e:  # noqa: BLE001
        enc.kill()
        emit(a.json, type="error", message=str(e))
        sys.exit(1)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def stream_raw(a, jobs, rate, threads, gpu):
    """Sintetiza en orden y escribe el audio por stdout a medida que está listo.

    Sin procesos auxiliares: arrancarlos cuesta segundos y ambos motores ya van más
    rápido que el tiempo real, así que importa más que empiece a sonar enseguida.
    """
    import queue
    import threading

    signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # si el reproductor se cierra, terminar sin traza
    silence = lambda sec: b"\x00\x00" * int(rate * sec)  # noqa: E731
    out = sys.stdout.buffer
    texts = [j[0] for j in jobs]
    if a.voice.startswith("qwen:"):
        engine = QwenEngine(a.voice.split(":", 1)[1], a.speed, qwen_cfg(a), qwen_override(a))
        results = qwen_results(engine, texts, [j[4] for j in jobs], first=1)  # la primera frase sola para que suene cuanto antes
    else:
        _load_voice(a.voice, a.speed, threads, gpu)
        results = map(_synth, texts)

    # Generar por delante en otro hilo: si se escribe directamente, la tubería del reproductor
    # se llena, la síntesis se detiene mientras suena y luego hay pausas entre lotes
    q = queue.Queue()

    def producer():
        try:
            for pcm in results:
                q.put(pcm)
        except Exception as e:  # noqa: BLE001
            q.put(e)
        q.put(None)

    threading.Thread(target=producer, daemon=True).start()
    for pre, post in ((j[1], j[2]) for j in jobs):
        pcm = q.get()
        if pcm is None:
            break
        if isinstance(pcm, Exception):
            print(f"Error: {pcm}", file=sys.stderr)
            sys.exit(1)
        out.write(silence(pre) + pcm + silence(post))
        out.flush()


if __name__ == "__main__":
    main()
