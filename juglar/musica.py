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
    "solo": "Solo", "interludio": "Interlude",
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


def normalizar_letra(texto):
    """[Estribillo] → [Chorus], [Estrofa 2] → [Verse 2]…; el resto de la letra no se toca."""
    def cambiar(m):
        nombre, resto = m.group(1).strip(), (m.group(2) or "").strip()
        if resto[:1].isdigit():
            resto = " " + resto
        return f"[{ETIQUETAS.get(nombre.lower(), nombre)}{resto}]"
    return re.sub(r"\[\s*([^\]\d:]+?)\s*((?:\s*\d+)?(?:\s*:[^\]]*)?)\]", cambiar, texto)


# Cabecera de un .md de canción: «Clave: valor» entre el título y la letra (ver docs/GUIA.md, sección 8)
CLAVES = {
    "estilo": "descripcion", "descripcion": "descripcion", "como suena": "descripcion", "musica": "descripcion",
    "genero": "extra", "voz": "extra", "voces": "extra", "instrumentos": "extra", "ambiente": "extra",
    "ritmo": "extra", "duracion": "duracion", "idioma": "idioma", "semilla": "semilla", "tempo": "bpm",
    "bpm": "bpm", "tonalidad": "tonalidad", "tono": "tonalidad", "instrumental": "instrumental",
    "titulo": "titulo",
}
SI = ("si", "sí", "s", "yes", "true", "1")


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


NOTAS = {"do": "C", "re": "D", "mi": "E", "fa": "F", "sol": "G", "la": "A", "si": "B"}


def _tonalidad(v):
    """«Re mayor» → «D Major», «la menor» → «A minor», «fa sostenido menor» → «F# minor»; lo demás, tal cual."""
    t = _sin_tildes(v)
    m = re.fullmatch(r"(do|re|mi|fa|sol|la|si)\s*(#|sostenido|b|bemol)?\s*(mayor|menor)?", t)
    if not m:
        return v.strip()
    nota = NOTAS[m[1]] + {"#": "#", "sostenido": "#", "b": "b", "bemol": "b"}.get(m[2] or "", "")
    return f"{nota} {'minor' if m[3] == 'menor' else 'Major'}"


def _letra_md(texto):
    """Encabezados de Markdown («## Estribillo», «**Estribillo**») → etiquetas [Estribillo]."""
    texto = re.sub(r"^#+\s*(.+?)\s*$", lambda m: f"[{m.group(1)}]", texto, flags=re.M)
    return re.sub(r"^\*\*(.+?)\*\*\s*$", lambda m: f"[{m.group(1)}]" if len(m.group(1)) < 30 else m.group(0),
                  texto, flags=re.M)


def leer_cancion(path):
    """Lee una canción de un .md/.txt → {titulo, descripcion, letra, duracion, idioma, semilla, bpm, tonalidad,
    instrumental}. Formato (todo opcional salvo la letra o el estilo):

        # El juglar
        Estilo: balada folk con guitarra española y voz masculina cálida
        Duración: 2:30
        Idioma: español
        Semilla: azar

        [Estrofa]
        Por el camino de piedra…

    La cabecera son líneas «Clave: valor» (o «> texto», que se suma al estilo) justo después del título; la
    primera línea que no lo es empieza la letra. También vale una cabecera entre «---» al principio."""
    path = Path(path)
    texto = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff").replace("\r\n", "\n").strip()
    c = {"titulo": path.stem, "descripcion": "", "letra": "", "duracion": None, "idioma": None, "semilla": None,
         "bpm": None, "tonalidad": "", "instrumental": False}
    lineas = texto.split("\n")
    i = 0
    if lineas and lineas[0].strip() == "---":  # cabecera al estilo YAML
        fin = next((k for k in range(1, len(lineas)) if lineas[k].strip() == "---"), None)
        if fin:
            cab, lineas = lineas[1:fin], lineas[fin + 1:]
            lineas = [x for x in cab if x.strip()] + [""] + lineas
    while i < len(lineas) and not lineas[i].strip():
        i += 1
    if i < len(lineas) and (m := re.match(r"#\s+(.+)", lineas[i])):
        c["titulo"] = m[1].strip()
        i += 1
    extra, cita = [], False
    while i < len(lineas):
        linea = lineas[i].strip()
        if not linea:
            i += 1
            cita = False
            continue
        if linea.startswith(">"):
            sep = " " if cita else ", "
            c["descripcion"] = (c["descripcion"] + (sep if c["descripcion"] else "") + linea.lstrip("> ").strip())
            i += 1
            cita = True
            continue
        cita = False
        m = re.match(r"[-*]?\s*\**([^:\[\]]{2,20}?)\**\s*:\s*(.*)$", linea)
        clave = CLAVES.get(_sin_tildes(m[1])) if m else None
        if not clave:
            break  # aquí empieza la letra
        valor = m[2].strip()
        if clave == "descripcion":
            c["descripcion"] = (c["descripcion"] + (", " if c["descripcion"] else "") + valor).strip()
        elif clave == "extra":
            extra.append(f"{_sin_tildes(m[1]) if _sin_tildes(m[1]) not in ('voz', 'voces') else 'voz'} {valor}")
        elif clave == "duracion":
            c["duracion"] = _duracion(valor)
        elif clave == "idioma":
            c["idioma"] = _idioma(valor)
        elif clave == "semilla":
            c["semilla"] = -1 if _sin_tildes(valor) in ("azar", "al azar", "aleatoria", "-1", "") else int(valor)
        elif clave == "bpm":
            c["bpm"] = int(re.sub(r"\D", "", valor) or 0) or None
        elif clave == "tonalidad":
            c["tonalidad"] = _tonalidad(valor)
        elif clave == "instrumental":
            c["instrumental"] = _sin_tildes(valor) in SI
        elif clave == "titulo":
            c["titulo"] = valor
        i += 1
    if extra:
        c["descripcion"] = ", ".join([x for x in [c["descripcion"]] if x] + extra)
    c["letra"] = _letra_md("\n".join(lineas[i:]).strip())
    if c["letra"].strip().lower() == "[instrumental]":
        c["letra"], c["instrumental"] = "", True
    return c


def leer_letra(path):
    """Compatibilidad: → (título, letra)."""
    c = leer_cancion(path)
    return c["titulo"], c["letra"]


def escribir_cancion(c):
    """El texto .md de una canción (lo contrario de leer_cancion)."""
    cab = [f"# {c.get('titulo') or 'Canción'}", ""]
    if c.get("descripcion"):
        cab.append(f"Estilo: {c['descripcion']}")
    d = int(c.get("duracion") or 0)
    cab.append(f"Duración: {d // 60}:{d % 60:02d}" if d else "Duración: auto")
    nombre = dict(IDIOMAS).get(c.get("idioma") or "es", c.get("idioma"))
    cab.append(f"Idioma: {nombre.lower()}")
    s = c.get("semilla")
    cab.append(f"Semilla: {s}" if s is not None and int(s) >= 0 else "Semilla: azar")
    if c.get("bpm"):
        cab.append(f"Tempo: {c['bpm']}")
    if c.get("tonalidad"):
        cab.append(f"Tonalidad: {c['tonalidad']}")
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
