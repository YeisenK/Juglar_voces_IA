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


def leer_letra(path):
    """Lee una letra de un .txt/.md. Si empieza con «# Título», lo devuelve aparte. → (título, letra)."""
    path = Path(path)
    texto = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").strip()
    titulo = path.stem
    m = re.match(r"#+\s*(.+)\n", texto + "\n")
    if m:
        titulo = m.group(1).strip()
        texto = texto[m.end():].strip()
    # los encabezados de Markdown («## Estribillo») también valen como etiquetas
    texto = re.sub(r"^#+\s*(.+?)\s*$", lambda m: f"[{m.group(1)}]", texto, flags=re.M)
    texto = re.sub(r"^\*\*(.+?)\*\*\s*$", lambda m: f"[{m.group(1)}]" if len(m.group(1)) < 30 else m.group(0),
                   texto, flags=re.M)
    return titulo, texto


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
