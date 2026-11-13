#!/usr/bin/env python3
"""Genera una canción con ACE-Step 1.5 (letra + descripción en lenguaje natural).

Uso: musica_worker.py PETICION.json

Se ejecuta con el Python del entorno de ACE-Step (<JUGLAR_DATA>/acestep/.venv). La petición:
  {"salida": "/ruta/Canción.mp3",       dónde guardar (mp3, flac, wav u ogg)
   "descripcion": "balada folk …",      estilo, instrumentos, voz, ambiente (lenguaje natural)
   "letra": "[Verse]\\n…",               letra con [Verse], [Chorus]… o vacía / [Instrumental]
   "instrumental": false,
   "idioma": "es",                      idioma de la voz cantada
   "duracion": 120,                     segundos (10-600); 0 o nada = la que elija el modelo
   "semilla": -1,                       -1 = al azar
   "bpm": null, "clave": "D minor",     opcionales: tempo, tonalidad
   "compas": "3"}                       2, 3, 4 o 6 (3/4, 6/8…)

Salida por stdout, una línea JSON por evento (el mismo protocolo que md2audio --json):
  {"type": "progress", "done": N, "total": 100, "fase": "…"}
  {"type": "done", "duration": segundos, "seed": semilla}   o   {"type": "error", "message": "…"}
Junto a la canción deja «.NOMBRE.ext.musica.json» con la petición, la semilla y lo que decidió el modelo.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

# Los eventos salen por una copia privada de stdout; lo que impriman las librerías va a stderr
_OUT = os.fdopen(os.dup(1), "w")
os.dup2(2, 1)
sys.stdout = sys.stderr

ACESTEP = Path(sys.prefix).resolve().parent      # <DATA>/acestep (el entorno es <DATA>/acestep/.venv)
sys.path.insert(0, str(ACESTEP))
os.chdir(ACESTEP)

FORMATOS = {"mp3": "mp3", "flac": "flac", "wav": "wav", "ogg": "opus", "opus": "opus"}


def emit(**kw):
    _OUT.write(json.dumps(kw, ensure_ascii=False) + "\n")
    _OUT.flush()


def fase(pct, texto):
    emit(type="progress", done=int(pct), total=100, fase=texto)


def duracion_de(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return None


# Calidades: modelo de música (DiT), pasos, compositor (LM) y tomas (se queda la que mejor canta la letra)
CALIDADES = {
    "rapida": {"modelo": "acestep-v15-turbo", "pasos": 8, "lm": "acestep-5Hz-lm-0.6B", "tomas": 1},
    "alta": {"modelo": "acestep-v15-sft", "pasos": 50, "lm": "acestep-5Hz-lm-1.7B", "tomas": 3},
}
WHISPER_PY = ACESTEP.parent / "whisper/bin/python"
LETRA_CANTADA = Path(__file__).resolve().parent / "letra_cantada.py"


def medir_letra(letra, audios, idioma):
    """Con Whisper: qué parte de la letra se canta en cada audio → {audio: cobertura (0-1) o None}."""
    if not WHISPER_PY.exists() or not LETRA_CANTADA.exists():
        return {}
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(letra)
    try:
        r = subprocess.run([str(WHISPER_PY), str(LETRA_CANTADA), f.name, *map(str, audios)], capture_output=True,
                           text=True, env={**os.environ, "IDIOMA": idioma}, timeout=1800)
        out = {}
        for linea in r.stdout.splitlines():
            try:
                d = json.loads(linea)
                out[d["audio"]] = d.get("cobertura")
            except ValueError:
                pass
        return out
    except Exception:  # noqa: BLE001
        return {}
    finally:
        os.unlink(f.name)


def main():
    pet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    salida = Path(pet["salida"])
    ext = salida.suffix.lstrip(".").lower() or "mp3"
    formato = FORMATOS.get(ext, "flac")
    cal = {**CALIDADES.get(pet.get("calidad") or "rapida", CALIDADES["rapida"]),
           **{k: pet[k] for k in ("modelo", "pasos", "lm", "tomas") if pet.get(k)}}
    turbo = "turbo" in cal["modelo"]

    fase(1, "Preparando ACE-Step…")
    import gc
    import torch
    from acestep.gpu_config import get_gpu_config, set_global_gpu_config
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler
    from acestep.model_downloader import (check_main_model_exists, check_model_exists, ensure_dit_model,
                                          ensure_lm_model, ensure_main_model, get_checkpoints_dir)

    gpu = get_gpu_config()
    set_global_gpu_config(gpu)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    offload = device == "cuda" and 0 < gpu.gpu_memory_gb < 16
    ckpt = get_checkpoints_dir()

    if not check_main_model_exists(ckpt):
        fase(2, "Descargando el modelo de música (solo la primera vez, varios GB)…")
        ok, msg = ensure_main_model(ckpt)
        if not ok:
            raise RuntimeError(f"No se pudo descargar el modelo: {msg}")
    if not check_model_exists(cal["modelo"], ckpt):
        fase(3, f"Descargando {cal['modelo']} (solo la primera vez)…")
        ok, msg = ensure_dit_model(cal["modelo"], ckpt)
        if not ok:
            raise RuntimeError(f"No se pudo descargar {cal['modelo']}: {msg}")

    fase(5, "Cargando el modelo de música…")
    dit = AceStepHandler()
    msg, ok = dit.initialize_service(project_root=str(ACESTEP), config_path=cal["modelo"], device=device,
                                     offload_to_cpu=offload, offload_dit_to_cpu=gpu.offload_dit_to_cpu_default,
                                     quantization="int8_weight_only" if gpu.quantization_default else None)
    if not ok:
        raise RuntimeError(f"No se pudo cargar ACE-Step: {msg}")

    # El compositor (LM) planifica la canción: estructura, melodía, dónde va cada verso, tempo y tonalidad
    llm, thinking, lm = LLMHandler(), bool(gpu.init_lm_default) or cal["lm"] != "acestep-5Hz-lm-0.6B", cal["lm"]
    if thinking:
        fase(10, "Cargando el compositor…")
        if not check_model_exists(lm, ckpt):
            ok, msg = ensure_lm_model(lm, checkpoints_dir=ckpt)
            if not ok:
                lm = "acestep-5Hz-lm-0.6B"
        msg, ok = llm.initialize(checkpoint_dir=str(ckpt), lm_model_path=lm, backend="pt", device=device,
                                 offload_to_cpu=offload)
        if not ok and lm != "acestep-5Hz-lm-0.6B":  # no cupo: el pequeño
            lm = "acestep-5Hz-lm-0.6B"
            msg, ok = llm.initialize(checkpoint_dir=str(ckpt), lm_model_path=lm, backend="pt", device=device,
                                     offload_to_cpu=offload)
        thinking = ok

    letra = (pet.get("letra") or "").strip()
    instrumental = bool(pet.get("instrumental")) or not letra or letra.lower() == "[instrumental]"
    dur = float(pet.get("duracion") or 0)
    tope = gpu.max_duration_with_lm if thinking else gpu.max_duration_without_lm
    if dur > 0:
        dur = max(10.0, min(dur, float(tope or 600)))
    semilla = int(pet.get("semilla", -1))
    tomas = max(1, int(cal["tomas"]))

    traducir = (("Generating music", "Generando la música…"), ("Decoding", "Pasando a audio…"),
                ("Preparing audio", "Guardando…"), ("Preparing", "Preparando…"), ("LM", "Componiendo…"))
    t0 = time.time()
    hechas = []   # (ruta, semilla, metadatos del compositor)
    with tempfile.TemporaryDirectory(prefix="juglar-musica-") as tmp:
        for k in range(tomas):
            base, ancho = 15 + 70 * k / tomas, 70 / tomas
            sufijo = f" (toma {k + 1} de {tomas})" if tomas > 1 else ""

            def progreso(valor, desc=None, **_):
                texto = next((es for en, es in traducir if desc and en.lower() in desc.lower()), "Generando…")
                try:
                    fase(base + ancho * float(valor), texto.rstrip("…") + sufijo + "…")
                except (TypeError, ValueError):
                    pass

            s_k = semilla + k if semilla >= 0 else -1
            params = GenerationParams(
                task_type="text2music", caption=(pet.get("descripcion") or "")[:4000],  # el compositor la resume
                lyrics="[Instrumental]" if instrumental else letra[:4096], instrumental=instrumental,
                vocal_language=pet.get("idioma") or "es", duration=dur if dur > 0 else -1.0,
                bpm=pet.get("bpm") or None, keyscale=pet.get("clave") or pet.get("tonalidad") or "",
                timesignature=str(pet.get("compas") or ""), inference_steps=int(cal["pasos"]),
                shift=3.0 if turbo else 1.0, guidance_scale=1.0 if turbo else float(pet.get("guia") or 7.0),
                seed=s_k, thinking=thinking, use_cot_language=False)
            config = GenerationConfig(batch_size=1, audio_format=formato, use_random_seed=s_k < 0,
                                      seeds=None if s_k < 0 else [s_k], mp3_bitrate="192k")
            fase(base, ("Componiendo" if thinking else "Generando") + sufijo + "…")
            res = generate_music(dit, llm, params, config, save_dir=tmp, progress=progreso)
            if not res.success or not res.audios:
                raise RuntimeError(res.error or res.status_message or "ACE-Step no devolvió audio")
            audio = res.audios[0]
            ruta = Path(tmp) / f"toma{k + 1}{Path(audio['path']).suffix}"
            shutil.move(audio["path"], ruta)
            meta_lm = res.extra_outputs.get("lm_metadata") if isinstance(res.extra_outputs, dict) else None
            hechas.append((ruta, (audio.get("params") or {}).get("seed", s_k),
                           {kk: v for kk, v in (meta_lm or {}).items()
                            if isinstance(v, (str, int, float, bool, type(None)))}))
        segundos = round(time.time() - t0, 1)

        # elegir la toma que mejor canta la letra (Whisper); con una sola, se mide igualmente para informar
        coberturas = {}
        if not instrumental:
            fase(86, "Escuchando qué toma canta mejor la letra…" if tomas > 1 else "Comprobando la letra cantada…")
            del dit, llm
            gc.collect()
            if device == "cuda":
                torch.cuda.empty_cache()
            coberturas = medir_letra(letra, [h[0] for h in hechas], pet.get("idioma") or "es")
        elegida = max(range(len(hechas)), key=lambda n: (coberturas.get(str(hechas[n][0])) or 0, -n))
        ruta, semilla_usada, decidido = hechas[elegida]
        salida.parent.mkdir(parents=True, exist_ok=True)
        if ruta.suffix.lstrip(".") == ext or formato == ext:
            shutil.move(str(ruta), salida)
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ruta), str(salida)], check=True)

    cob = coberturas.get(str(hechas[elegida][0]))
    meta = {**pet, "semilla_usada": semilla_usada, "segundos_generando": segundos,
            "modelo": f"ACE-Step 1.5 · {cal['modelo'].replace('acestep-v15-', '')} · {cal['pasos']} pasos",
            "compositor": lm if thinking else None, "fecha": time.time(), "decidido": decidido,
            "letra_cantada": cob,
            "tomas": [{"semilla": h[1], "letra_cantada": coberturas.get(str(h[0]))} for h in hechas]}
    salida.with_name(f".{salida.name}.musica.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                                                 encoding="utf-8")
    emit(type="done", duration=duracion_de(salida), seed=semilla_usada, letra_cantada=cob)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        emit(type="error", message=str(e) or e.__class__.__name__)
        sys.exit(1)
