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


def main():
    pet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    salida = Path(pet["salida"])
    ext = salida.suffix.lstrip(".").lower() or "mp3"
    formato = FORMATOS.get(ext, "flac")

    fase(1, "Preparando ACE-Step…")
    import torch
    from acestep.gpu_config import get_gpu_config, set_global_gpu_config
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler
    from acestep.model_downloader import (check_main_model_exists, ensure_lm_model, ensure_main_model,
                                          get_checkpoints_dir)

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

    fase(5, "Cargando el modelo de música…")
    dit = AceStepHandler()
    msg, ok = dit.initialize_service(project_root=str(ACESTEP), config_path="acestep-v15-turbo", device=device,
                                     offload_to_cpu=offload, offload_dit_to_cpu=gpu.offload_dit_to_cpu_default,
                                     quantization="int8_weight_only" if gpu.quantization_default else None)
    if not ok:
        raise RuntimeError(f"No se pudo cargar ACE-Step: {msg}")

    # El modelo de lenguaje (LM) planifica la canción: estructura, tempo, tonalidad y la descripción
    llm, thinking = LLMHandler(), bool(gpu.init_lm_default)
    if thinking:
        fase(10, "Cargando el compositor (LM)…")
        modelos = llm.get_available_5hz_lm_models()
        lm = gpu.recommended_lm_model or (modelos[0] if modelos else None) or "acestep-5Hz-lm-0.6B"
        if lm not in modelos:
            ok, msg = ensure_lm_model(lm, checkpoints_dir=ckpt)
            if not ok:
                thinking = False
        if thinking:
            msg, ok = llm.initialize(checkpoint_dir=str(ckpt), lm_model_path=lm, backend="pt", device=device,
                                     offload_to_cpu=offload)
            thinking = ok

    letra = (pet.get("letra") or "").strip()
    instrumental = bool(pet.get("instrumental")) or not letra or letra.lower() == "[instrumental]"
    dur = float(pet.get("duracion") or 0)
    tope = gpu.max_duration_with_lm if thinking else gpu.max_duration_without_lm
    if dur > 0:
        dur = max(10.0, min(dur, float(tope or 600)))
    params = GenerationParams(
        task_type="text2music", caption=(pet.get("descripcion") or "")[:4000],  # el compositor (LM) la resume
        lyrics="[Instrumental]" if instrumental else letra[:4096], instrumental=instrumental,
        vocal_language=pet.get("idioma") or "es", duration=dur if dur > 0 else -1.0,
        bpm=pet.get("bpm") or None, keyscale=pet.get("clave") or pet.get("tonalidad") or "",
        timesignature=str(pet.get("compas") or ""),
        inference_steps=8, shift=3.0, seed=int(pet.get("semilla", -1)), thinking=thinking,
        use_cot_language=False)
    config = GenerationConfig(batch_size=1, audio_format=formato, use_random_seed=int(pet.get("semilla", -1)) < 0,
                              seeds=None if int(pet.get("semilla", -1)) < 0 else [int(pet["semilla"])],
                              mp3_bitrate="192k")

    traducir = (("Generating music", "Generando la música…"), ("Decoding", "Pasando a audio…"),
                ("Preparing audio", "Guardando…"), ("Preparing", "Preparando…"), ("LM", "Componiendo…"))

    def progreso(valor, desc=None, **_):
        texto = next((es for en, es in traducir if desc and en.lower() in desc.lower()), "Generando…")
        try:
            fase(15 + 84 * float(valor), texto)
        except (TypeError, ValueError):
            pass

    fase(15, "Componiendo…" if thinking else "Generando…")
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="juglar-musica-") as tmp:
        res = generate_music(dit, llm, params, config, save_dir=tmp, progress=progreso)
        if not res.success or not res.audios:
            raise RuntimeError(res.error or res.status_message or "ACE-Step no devolvió audio")
        audio = res.audios[0]
        origen = Path(audio["path"])
        salida.parent.mkdir(parents=True, exist_ok=True)
        if origen.suffix.lstrip(".") == ext or formato == ext:
            shutil.move(str(origen), salida)
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(origen), str(salida)], check=True)

    usados = audio.get("params") or {}
    semilla = usados.get("seed", pet.get("semilla"))
    meta = {**pet, "semilla_usada": semilla, "segundos_generando": round(time.time() - t0, 1),
            "modelo": "ACE-Step 1.5 turbo", "compositor": thinking, "fecha": time.time(),
            "decidido": {k: v for k, v in (res.extra_outputs.get("lm_metadata") or {}).items()
                         if isinstance(v, (str, int, float, bool, type(None)))}
            if isinstance(res.extra_outputs, dict) else {}}
    salida.with_name(f".{salida.name}.musica.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                                                 encoding="utf-8")
    emit(type="done", duration=duracion_de(salida), seed=semilla)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        emit(type="error", message=str(e) or e.__class__.__name__)
        sys.exit(1)
