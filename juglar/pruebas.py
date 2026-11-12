#!/usr/bin/env python3
"""Pruebas de voz guardadas: el texto estándar leído por cada voz y cada personaje, generado una sola vez.

Cada prueba es pruebas/<nombre>.wav con su clave en pruebas/<nombre>.json. La clave depende del texto, de la
voz (y de su grabación de referencia) y de sus ajustes: si cambia algo, la prueba se vuelve a generar.

Uso: pruebas.py            genera las que falten o estén desfasadas (voces de Qwen y personajes)
     pruebas.py --todas    también las de Piper y Kokoro
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))
import md2audio  # noqa: E402

import rutas  # noqa: E402

VENV_PY = rutas.VENV_PY
MD2AUDIO = APP_DIR / "md2audio.py"
DIR = rutas.PRUEBAS
PRUEBA_VOZ = rutas.PRUEBA_VOZ   # texto estándar (editable)
TEXTO_DE_SERIE = ("Cuando Elena llegó a la casa del acantilado, el sol ya se escondía detrás del mar.\n\n"
                  "—¿Hay alguien aquí? ¿Por qué está abierta la puerta? —preguntó en voz baja.\n\n"
                  "—¡No puede ser! ¡Por fin has vuelto! —gritó su abuela desde la cocina.\n\n"
                  "Se abrazaron un largo rato, mientras afuera el viento seguía golpeando las ventanas.")


def texto():
    try:
        return PRUEBA_VOZ.read_text(encoding="utf-8").strip() or TEXTO_DE_SERIE
    except OSError:
        return TEXTO_DE_SERIE


def _ref_stamp(perfil):
    try:
        st = (md2audio.QWEN_VOICES / perfil / "ref.wav").stat()
        return f"{st.st_size}-{int(st.st_mtime)}"
    except OSError:
        return ""


def receta(spec):
    """(nombre del archivo, clave, argumentos de md2audio) para una voz «qwen:x», «piper…» o «personaje:slug»."""
    extra, velocidad, datos = [], 1.0, {"texto": texto(), "voz": spec}
    if spec.startswith("personaje:"):
        slug = spec.split(":", 1)[1]
        ficha = md2audio.elenco().get(slug)
        if not ficha:
            return None
        muestreo = {k: v for k, v in md2audio.ficha_ajustes(ficha).items() if k in md2audio.VOICE_KEYS}
        velocidad = ficha.get("velocidad", 1.0)
        propio = md2audio.qwen_settings(ficha["voz"])
        if velocidad == 1.0 and all(muestreo[k] == propio[k] for k in md2audio.VOICE_KEYS):
            return receta("qwen:" + ficha["voz"])  # suena igual que su voz: comparten la prueba
        voz = "qwen:" + ficha["voz"]
        extra = ["--qwen-ajustes", json.dumps(muestreo)]
        datos.update(base=voz, muestreo=muestreo, velocidad=velocidad, ref=_ref_stamp(ficha["voz"]))
        nombre = f"personaje_{slug}"
    elif spec.startswith("qwen:"):
        perfil = spec.split(":", 1)[1]
        cfg = md2audio.qwen_settings(perfil)
        datos.update(muestreo={k: cfg[k] for k in md2audio.VOICE_KEYS}, ref=_ref_stamp(perfil))
        voz, nombre = spec, f"qwen_{perfil}"
    else:
        voz, nombre = spec, spec.replace(":", "_")
    clave = hashlib.sha1(json.dumps(datos, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return nombre, clave, ["-v", voz, "-s", f"{velocidad:.3f}", "--no-revisar", *extra]


def ruta(nombre):
    return DIR / f"{nombre}.wav"


def vigente(nombre, clave):
    """True si la prueba guardada existe y se generó con exactamente la misma voz, texto y ajustes."""
    try:
        return ruta(nombre).exists() and json.loads((DIR / f"{nombre}.json").read_text()).get("clave") == clave
    except (OSError, ValueError):
        return False


def comando(nombre, args):
    """Orden que genera la prueba en un archivo temporal (se da por buena con terminar())."""
    DIR.mkdir(parents=True, exist_ok=True)
    fuente = DIR / "_texto.md"
    fuente.write_text(texto(), encoding="utf-8")
    return [str(VENV_PY), "-I", str(MD2AUDIO), str(fuente), "-o", str(DIR / f"_{nombre}.wav"), "--sin-flash", *args]


def terminar(nombre, clave):
    """Pone en su sitio la prueba recién generada y apunta su clave."""
    tmp = DIR / f"_{nombre}.wav"
    if not tmp.exists():
        return False
    os.replace(tmp, ruta(nombre))
    (DIR / f"{nombre}.json").write_text(json.dumps({"clave": clave}))
    return True


def generar(spec, log=None):
    """Genera (si hace falta) la prueba de una voz o personaje. Devuelve la ruta o None si falló."""
    r = receta(spec)
    if r is None:
        return None
    nombre, clave, args = r
    if vigente(nombre, clave):
        return ruta(nombre)
    ok = subprocess.run(comando(nombre, args), stdout=subprocess.DEVNULL, stderr=log or subprocess.DEVNULL).returncode == 0
    return ruta(nombre) if ok and terminar(nombre, clave) else None


def main():
    specs = [f"personaje:{s}" for s in md2audio.elenco()] + [f"qwen:{p}" for p in md2audio.qwen_profiles()]
    if "--todas" in sys.argv:
        specs += [v for v in md2audio.list_voices() if not v.startswith("qwen:")]
    for spec in specs:
        r = receta(spec)
        if r and vigente(r[0], r[1]):
            print(f"ya estaba  {spec}", flush=True)
            continue
        print(("hecha      " if generar(spec) else "FALLÓ      ") + spec, flush=True)


if __name__ == "__main__":
    main()
