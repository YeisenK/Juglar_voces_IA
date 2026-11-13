"""Música con ACE-Step: canciones guardadas, letras y ejemplos de descripción.

Las canciones se guardan en ~/Música/Juglar (rutas.MUSICA). Junto a cada una, el generador deja
«.NOMBRE.ext.musica.json» con la letra, la descripción y la semilla, para poder repetirla o variarla.
"""
import json
import re
from pathlib import Path

import rutas

AUDIO_EXTS = (".mp3", ".flac", ".wav", ".ogg", ".opus")

# Las etiquetas de la letra se pueden escribir en español; ACE-Step las entiende en inglés
ETIQUETAS = {
    "estrofa": "Verse", "verso": "Verse", "estribillo": "Chorus", "coro": "Chorus", "puente": "Bridge",
    "introducción": "Intro", "introduccion": "Intro", "intro": "Intro", "final": "Outro", "cierre": "Outro",
    "outro": "Outro", "preestribillo": "Pre-Chorus", "pre-estribillo": "Pre-Chorus", "instrumental": "Instrumental",
    "solo": "Solo", "interludio": "Interlude", "despedida": "Outro", "coda": "Outro", "verse": "Verse",
    "chorus": "Chorus", "bridge": "Bridge", "pre-chorus": "Pre-Chorus", "interlude": "Interlude",
}

EJEMPLOS = [
    ("Balada folk", "balada folk acústica, guitarra española y voz masculina cálida, tempo lento, íntima"),
    ("Taberna medieval", "música medieval de taberna, laúd, flauta y pandero, voz masculina alegre, ritmo bailable"),
    ("Épica", "épica orquestal, coros, tambores de guerra y cuerdas, voz femenina potente, ambiente de batalla"),
    ("Canción de cuna", "canción de cuna suave, piano y caja de música, voz femenina dulce y susurrada"),
    ("Pop en español", "pop latino moderno, guitarra y percusión, voz femenina clara, estribillo pegadizo"),
    ("Rock", "rock en español con guitarras eléctricas, batería enérgica y voz masculina rasgada"),
    ("Bolero", "bolero romántico con requinto, guitarras y voz masculina melancólica"),
    ("Lamento", "lamento triste con violonchelo y piano, voz femenina suave, lento y emotivo"),
]

IDIOMAS = [("es", "Español"), ("en", "Inglés"), ("pt", "Portugués"), ("fr", "Francés"), ("it", "Italiano"),
           ("de", "Alemán"), ("ca", "Catalán"), ("la", "Latín"), ("ja", "Japonés")]


def meta_de(audio):
    return Path(audio).with_name(f".{Path(audio).name}.musica.json")


def _etiqueta(nombre):
    """«Estrofa 2» → «Verse 2», «Estribillo final» → «Chorus», «Despedida» → «Outro»; desconocida → tal cual."""
    palabras = nombre.strip().split()
    if not palabras:
        return nombre
    base = ETIQUETAS.get(palabras[0].lower()) or ETIQUETAS.get(nombre.strip().lower())
    if not base:
        return nombre.strip()
    num = next((p for p in palabras[1:] if p.isdigit()), "")
    return f"{base} {num}".strip()


def separar_letra(texto):
    """Prepara la letra para ACE-Step: las etiquetas se quedan solo con su nombre en inglés
    («[Estrofa 2: coro de niñas, entra la flauta]» → «[Verse 2]»), porque si llevan instrucciones el modelo
    las canta. → (letra, notas) con notas = ["Estrofa 2: coro de niñas, entra la flauta", …] para la descripción."""
    notas = []

    def cambiar(m):
        dentro = m.group(1)
        nombre, _, nota = dentro.partition(":")
        if not nota:  # también «[Estribillo - suave]» o «[Estribillo (todos)]»
            if mm := re.match(r"\s*([^\-–—(]+?)\s*(?:[-–—]|\()\s*(.+?)\)?\s*$", dentro):
                nombre, nota = mm.group(1), mm.group(2)
        if nota.strip():
            notas.append(f"{nombre.strip()}: {nota.strip()}")
        return f"[{_etiqueta(nombre)}]"
    return re.sub(r"\[([^\]\n]+)\]", cambiar, texto), notas


def normalizar_letra(texto):
    """Solo la letra de separar_letra (etiquetas en inglés y sin instrucciones)."""
    return separar_letra(texto)[0]


# Cabecera de un .md de canción: «Clave: valor» entre el título y la letra (ver docs/GUIA.md, sección 8).
# Cada clave va a su campo; las de sonido (estilo, voz, instrumentos…) forman juntas la descripción.
CAMPOS = ("estilo", "voz", "instrumentos", "ambiente", "tempo", "tonalidad")   # los de «cómo suena», en orden
CLAVES = {
    "estilo": "estilo", "descripcion": "estilo", "como suena": "estilo", "musica": "estilo", "genero": "estilo",
    "voz": "voz", "voces": "voz", "instrumentos": "instrumentos", "instrumentacion": "instrumentos",
    "ambiente": "ambiente", "atmosfera": "ambiente", "tempo": "tempo", "ritmo": "tempo", "bpm": "tempo",
    "compas": "tempo", "tonalidad": "tonalidad", "tono": "tonalidad", "duracion": "duracion",
    "idioma": "idioma", "semilla": "semilla", "instrumental": "instrumental", "titulo": "titulo",
    "calidad": "calidad",
}
# Calidades del generador (motores/musica_worker.py): (clave, nombre en la app)
CALIDADES = [("alta", "Alta · 3 tomas, elige la que mejor canta la letra (lenta)"),
             ("rapida", "Rápida · una toma (para probar)")]
CALIDAD_POR_DEFECTO = "alta"


def _calidad(v):
    v = _sin_tildes(v)
    if v in ("rapida", "turbo", "baja", "prueba", "borrador"):
        return "rapida"
    if v in ("alta", "buena", "maxima", "final", "sft"):
        return "alta"
    raise ValueError(f"Calidad desconocida: «{v}» (usa «alta» o «rápida»)")
NOMBRES = {"estilo": "Estilo", "voz": "Voz", "instrumentos": "Instrumentos", "ambiente": "Ambiente",
           "tempo": "Tempo", "tonalidad": "Tonalidad"}
SI = ("si", "sí", "s", "yes", "true", "1")
NOTAS = {"do": "C", "re": "D", "mi": "E", "fa": "F", "sol": "G", "la": "A", "si": "B"}


def _sin_tildes(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn").strip()


def _duracion(v):
    """«2:30», «150», «150 s», «2 min», «2 min 30 s», «auto» → segundos (0 = automática)."""
    v = _sin_tildes(v)
    if v in ("", "auto", "automatica", "0"):
        return 0
    if m := re.fullmatch(r"(\d+):(\d{1,2})", v):
        return int(m[1]) * 60 + int(m[2])
    if m := re.fullmatch(r"(?:(\d+)\s*(?:min|minutos?|m))?\s*(?:(\d+)\s*(?:s|seg|segundos?))?", v):
        if m[1] or m[2]:
            return int(m[1] or 0) * 60 + int(m[2] or 0)
    if v.isdigit():
        return int(v)
    raise ValueError(f"Duración no válida: «{v}» (usa 2:30, 150, «2 min» o «auto»)")


def _idioma(v):
    v = _sin_tildes(v)
    for code, nombre in IDIOMAS:
        if v in (code, _sin_tildes(nombre)):
            return code
    raise ValueError(f"Idioma desconocido: «{v}» (usa {', '.join(n for _c, n in IDIOMAS)})")


def bpm_de(tempo):
    """«lento, 72 BPM, compás de 3/4» → 72; «120» → 120; si no hay un número claro, None."""
    t = _sin_tildes(tempo or "")
    m = re.search(r"(\d{2,3})\s*(?:bpm|pulsos|ppm|negras)", t) or re.fullmatch(r"\s*(\d{2,3})\s*", t)
    return int(m[1]) if m and 30 <= int(m[1]) <= 300 else None


def compas_de(tempo):
    """«compás de 3/4» → «3»; «6/8» → «6» (lo que entiende ACE-Step: 2, 3, 4 o 6)."""
    m = re.search(r"\b([2346])\s*/\s*(?:4|8)\b", tempo or "")
    return m[1] if m else ""


def tonalidad_de(texto):
    """Busca la tonalidad en un texto libre: «menor (re menor), cadencias suaves» → «D minor»,
    «sol mayor» → «G Major», «Am» o «C Major» tal cual. Los modos («dórico en mi») no tienen equivalente: ""."""
    t = _sin_tildes(texto or "")
    m = re.search(r"\b(do|re|mi|fa|sol|la|si)\s*(#|sostenido|bemol|b)?\s+(mayor|menor)\b", t)
    if m:
        nota = NOTAS[m[1]] + {"#": "#", "sostenido": "#", "b": "b", "bemol": "b"}.get(m[2] or "", "")
        return f"{nota} {'minor' if m[3] == 'menor' else 'Major'}"
    m = re.fullmatch(r"\s*([A-Ga-g][#b]?)\s*(major|minor|m)?\s*", texto or "")
    if m:
        return f"{m[1].upper()} {'minor' if (m[2] or '').lower() in ('minor', 'm') else 'Major'}"
    return ""


def descripcion_de(c):
    """La descripción que recibe ACE-Step: el estilo y, detrás, cada detalle con su nombre."""
    partes = [c.get("estilo", "").strip().rstrip(".")]
    partes += [f"{NOMBRES[k]}: {c[k].strip().rstrip('.')}" for k in CAMPOS[1:] if (c.get(k) or "").strip()]
    return ". ".join(p for p in partes if p)


def _letra_md(texto):
    """Encabezados de Markdown («## Estribillo», «**Estribillo**») → etiquetas [Estribillo]."""
    texto = re.sub(r"^#+\s*(.+?)\s*$", lambda m: f"[{m.group(1)}]", texto, flags=re.M)
    return re.sub(r"^\*\*(.+?)\*\*\s*$", lambda m: f"[{m.group(1)}]" if len(m.group(1)) < 30 else m.group(0),
                  texto, flags=re.M)


def nueva_cancion(titulo="Canción"):
    return {"titulo": titulo, **{k: "" for k in CAMPOS}, "letra": "", "duracion": None, "idioma": None,
            "semilla": None, "instrumental": False, "calidad": None}


def completar(c):
    """Añade lo que se deduce de los campos: descripcion, bpm, tonalidad para ACE-Step (clave) y compás."""
    c["descripcion"] = descripcion_de(c)
    c["bpm"] = bpm_de(c.get("tempo"))
    c["compas"] = compas_de(c.get("tempo"))
    c["clave"] = tonalidad_de(c.get("tonalidad"))
    return c


def leer_cancion(path):
    """Lee una canción de un .md/.txt → {titulo, estilo, voz, instrumentos, ambiente, tempo, tonalidad, letra,
    duracion, idioma, semilla, instrumental} + lo deducido (descripcion, bpm, compas, clave). Formato:

        # El juglar
        Estilo: balada folk con guitarra española
        Voz: masculina, cálida
        Instrumentos: guitarra, flauta
        Ambiente: taberna al anochecer
        Tempo: lento, 72 BPM, compás de 3/4
        Tonalidad: re menor
        Duración: 2:30
        Idioma: español
        Semilla: azar

        [Estrofa]
        Por el camino de piedra…

    La cabecera son líneas «Clave: valor» (o «> texto», que se suma al estilo) justo después del título; la
    primera línea que no lo es empieza la letra. También vale una cabecera entre «---» al principio."""
    path = Path(path)
    texto = path.read_text(encoding="utf-8", errors="replace").lstrip("﻿").replace("\r\n", "\n").strip()
    c = nueva_cancion(path.stem)
    lineas = texto.split("\n")
    if lineas and lineas[0].strip() == "---":  # cabecera al estilo YAML
        fin = next((k for k in range(1, len(lineas)) if lineas[k].strip() == "---"), None)
        if fin:
            lineas = [x for x in lineas[1:fin] if x.strip()] + [""] + lineas[fin + 1:]
    i = 0
    while i < len(lineas) and not lineas[i].strip():
        i += 1
    if i < len(lineas) and (m := re.match(r"#\s+(.+)", lineas[i])):
        c["titulo"] = m[1].strip()
        i += 1

    def sumar(campo, valor, sep="; "):
        c[campo] = (c[campo] + sep + valor) if c[campo] else valor

    cita = False
    while i < len(lineas):
        linea = lineas[i].strip()
        if not linea:
            i += 1
            cita = False
            continue
        if linea.startswith(">"):
            sumar("estilo", linea.lstrip("> ").strip(), " " if cita else "; ")
            i += 1
            cita = True
            continue
        cita = False
        m = re.match(r"[-*]?\s*\**([^:\[\]]{2,20}?)\**\s*:\s*(.*)$", linea)
        clave = CLAVES.get(_sin_tildes(m[1])) if m else None
        if not clave:
            break  # aquí empieza la letra
        valor = m[2].strip()
        if clave in CAMPOS:
            sumar(clave, valor)
        elif clave == "duracion":
            c["duracion"] = _duracion(valor)
        elif clave == "idioma":
            c["idioma"] = _idioma(valor)
        elif clave == "semilla":
            c["semilla"] = -1 if _sin_tildes(valor) in ("azar", "al azar", "aleatoria", "-1", "") else int(valor)
        elif clave == "instrumental":
            c["instrumental"] = _sin_tildes(valor) in SI
        elif clave == "calidad":
            c["calidad"] = _calidad(valor)
        elif clave == "titulo":
            c["titulo"] = valor
        i += 1
    c["letra"] = _letra_md("\n".join(lineas[i:]).strip())
    if c["letra"].strip().lower() == "[instrumental]":
        c["letra"], c["instrumental"] = "", True
    return completar(c)


def leer_letra(path):
    """Compatibilidad: → (título, letra)."""
    c = leer_cancion(path)
    return c["titulo"], c["letra"]


def escribir_cancion(c):
    """El texto .md de una canción (lo contrario de leer_cancion)."""
    cab = [f"# {c.get('titulo') or 'Canción'}", ""]
    if not any((c.get(k) or "").strip() for k in CAMPOS) and c.get("descripcion"):
        cab.append(f"Estilo: {c['descripcion']}")  # canciones de antes, con todo junto
    cab += [f"{NOMBRES[k]}: {c[k].strip()}" for k in CAMPOS if (c.get(k) or "").strip()]
    d = int(c.get("duracion") or 0)
    cab.append(f"Duración: {d // 60}:{d % 60:02d}" if d else "Duración: auto")
    nombre = dict(IDIOMAS).get(c.get("idioma") or "es", c.get("idioma"))
    cab.append(f"Idioma: {nombre.lower()}")
    s = c.get("semilla")
    cab.append(f"Semilla: {s}" if s is not None and int(s) >= 0 else "Semilla: azar")
    if c.get("calidad"):
        cab.append(f"Calidad: {'rápida' if c['calidad'] == 'rapida' else 'alta'}")
    letra = (c.get("letra") or "").strip() or "[Instrumental]"
    return "\n".join(cab) + "\n\n" + letra + "\n"


def canciones(carpeta=None):
    """Canciones de la carpeta de música, de la más reciente a la más antigua: [{audio, titulo, …}]."""
    carpeta = Path(carpeta or rutas.MUSICA)
    if not carpeta.is_dir():
        return []
    out = []
    for p in carpeta.iterdir():
        if p.suffix.lower() not in AUDIO_EXTS or p.name.startswith("."):
            continue
        try:
            meta = json.loads(meta_de(p).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        out.append({**meta, "audio": str(p), "titulo": meta.get("titulo") or p.stem, "mtime": p.stat().st_mtime})
    return sorted(out, key=lambda c: -c["mtime"])


def borrar(audio):
    """Manda una canción (y sus datos) a la papelera."""
    from gi.repository import Gio
    for p in (Path(audio), meta_de(audio)):
        if p.exists():
            Gio.File.new_for_path(str(p)).trash(None)


def nombre_archivo(titulo):
    limpio = re.sub(r'[\\/:*?"<>|]+', " ", titulo).strip() or "Canción"
    return re.sub(r"\s+", " ", limpio)[:80]
