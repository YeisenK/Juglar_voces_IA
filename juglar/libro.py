"""Libros por carpetas: una carpeta = un libro, cada archivo .md/.txt = un capítulo.

    Mi libro/
    ├── juglar.json          (opcional) ajustes del libro
    ├── 01 El bravo.md       capítulos, en orden natural por nombre (2 va antes que 10)
    ├── 02 La sala grande.md
    ├── _notas.md            lo que empieza por «_» o «.» no se lee
    └── audio/               aquí deja Juglar los audios: «01 El bravo.mp3», …

juglar.json (todo opcional):
    {"titulo": "Cid el conquistador",   nombre del libro en la cola (por defecto, el de la carpeta)
     "narrador": "narrador",             voz que narra: una voz de Qwen («narrador») o un nombre completo
                                         («qwen:narradora», «es_MX-claude-high»…); por defecto, la elegida en la app
     "formato": "mp3",                   mp3, ogg, m4b o wav
     "velocidad": 1.0,
     "carpeta_audio": "audio",           dónde van los audios, relativo al libro («.» = junto a cada capítulo)
     "omitir": ["borrador.md"]}          capítulos que no se exportan
"""
import json
import re
from pathlib import Path

EXTS = (".md", ".markdown", ".txt")
CONFIG = "juglar.json"
FORMATOS = ("mp3", "ogg", "m4b", "wav")


def orden_natural(path):
    """«Cap 2» antes que «Cap 10»."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


class Libro:
    def __init__(self, carpeta):
        self.carpeta = Path(carpeta).expanduser()
        if not self.carpeta.is_dir():
            raise ValueError(f"No es una carpeta: {carpeta}")
        cfg, f = {}, self.carpeta / CONFIG
        if f.exists():
            try:
                cfg = json.loads(f.read_text(encoding="utf-8"))
            except ValueError as e:
                raise ValueError(f"{f.name} no es un JSON válido: {e}") from None
        self.cfg = cfg
        self.titulo = cfg.get("titulo") or self.carpeta.name
        narrador = cfg.get("narrador")
        self.narrador = (narrador if ":" in narrador or "-" in narrador else f"qwen:{narrador}") if narrador else None
        self.formato = str(cfg.get("formato", "mp3")).lstrip(".").lower()
        if self.formato not in FORMATOS:
            raise ValueError(f"Formato desconocido en {CONFIG}: {self.formato} (usa {', '.join(FORMATOS)})")
        self.velocidad = float(cfg.get("velocidad", 1.0))
        self.carpeta_audio = cfg.get("carpeta_audio", "audio")
        omitir = set(cfg.get("omitir", []))
        self.capitulos = sorted(
            (p for p in self.carpeta.iterdir()
             if p.is_file() and p.suffix.lower() in EXTS and not p.name.startswith(("_", "."))
             and p.name not in omitir and p.stem not in omitir),
            key=orden_natural)
        if not self.capitulos:
            raise ValueError(f"La carpeta «{self.carpeta.name}» no tiene capítulos (.md o .txt)")

    def salida(self, capitulo, formato=None):
        """Dónde va el audio de un capítulo."""
        return self.carpeta / self.carpeta_audio / f"{capitulo.stem}.{(formato or self.formato).lstrip('.')}"

    def marcas_desconocidas(self):
        """[(capítulo, línea, marca)] de las «—@marca» que no son ni personaje ni voz, en todo el libro."""
        import md2audio
        return [(cap, n, m) for cap in self.capitulos
                for n, m in md2audio.marcas_desconocidas(cap.read_text(encoding="utf-8", errors="replace"))]
