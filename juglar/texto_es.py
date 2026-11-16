"""Prepara texto en español para que se lea como se dice, no como se escribe.

Cantidades, fechas, horas, ordinales, números romanos, abreviaturas, símbolos, rayas de diálogo
y un diccionario de pronunciación propio (pronunciacion.txt, una línea «Palabra = cómo se lee»).
"""
import re
from pathlib import Path

try:
    import rutas
    DICCIONARIO = rutas.DICCIONARIO
except ImportError:  # usado suelto, fuera de Juglar
    DICCIONARIO = Path(__file__).resolve().parent / "pronunciacion.txt"

# ---------------------------------------------------------------- números

_UNI = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce",
        "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno",
        "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho",
        "veintinueve"]
_DEC = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
_CEN = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos",
        "ochocientos", "novecientos"]


def _uno(w, fem, apoc):
    """«uno» -> «un» / «una» (también en veintiuno, treinta y uno…)."""
    if not w.endswith("uno"):
        return w
    if fem:
        return w[:-1] + "a"
    if apoc:
        return w[:-3] + "ún" if w.startswith("veinti") else w[:-1]
    return w


def _centenas(n, fem, apoc):
    if n == 100:
        return "cien"
    c, r = divmod(n, 100)
    parts = []
    if c:
        w = _CEN[c]
        parts.append(w.replace("ientos", "ientas") if fem and c >= 2 else w)
    if r:
        if r < 30:
            w = _UNI[r]
        else:
            d, u = divmod(r, 10)
            w = _DEC[d] + (" y " + _UNI[u] if u else "")
        parts.append(_uno(w, fem, apoc))
    return " ".join(parts)


def cardinal(n, fem=False, apoc=False):
    """Número entero en palabras; apoc=True da «un» (un libro), fem=True da «una» (una casa)."""
    if n == 0:
        return "cero"
    if n < 0:
        return "menos " + cardinal(-n, fem, apoc)
    if n < 1000:
        return _centenas(n, fem, apoc)
    if n < 10**6:
        m, r = divmod(n, 1000)
        head = "mil" if m == 1 else cardinal(m, fem, True) + " mil"
        return head + (" " + _centenas(r, fem, apoc) if r else "")
    if n < 10**12:
        m, r = divmod(n, 10**6)
        head = "un millón" if m == 1 else cardinal(m, False, True) + " millones"
        return head + (" " + cardinal(r, fem, apoc) if r else "")
    return " ".join(_UNI[int(d)] for d in str(n))  # cifras enormes: dígito a dígito


_MASC_EN_A = {"día", "días", "mapa", "mapas", "planeta", "planetas", "problema", "problemas", "sistema", "sistemas",
              "tema", "temas", "idioma", "idiomas", "programa", "programas", "poema", "poemas", "clima", "dilema",
              "esquema", "teorema", "cometa", "cometas", "papa", "yoga", "tranvía", "tranvías", "guía", "guías",
              "drama", "dramas", "diploma", "diplomas", "pijama", "pijamas", "sofá", "sofás", "café", "cafés"}


def _es_femenino(palabra):
    w = (palabra or "").lower()
    if not w or w in _MASC_EN_A:
        return False
    return w.endswith(("a", "as", "ción", "ciones", "sión", "siones", "dad", "dades", "tud", "tudes", "umbre"))


def _leer_entero(texto, siguiente=None):
    n = int(texto)
    if siguiente is not None and n % 10 == 1 and n % 100 != 11:
        return cardinal(n, fem=_es_femenino(siguiente), apoc=True)
    return cardinal(n)


def _decimales(frac):
    ceros = len(frac) - len(frac.lstrip("0"))
    resto = frac.lstrip("0")
    return " ".join(["cero"] * ceros + ([cardinal(int(resto))] if resto else []))


def _numero(entero, frac=None, siguiente=None):
    """'1.234' + ',5' -> «mil doscientos treinta y cuatro coma cinco»."""
    entero = entero.replace(".", "").replace(" ", "").replace(" ", "")
    palabras = _leer_entero(entero, None if frac else siguiente)
    return palabras + (" coma " + _decimales(frac) if frac else "")


# ---------------------------------------------------------------- ordinales y romanos

_ORD_M = ["", "primero", "segundo", "tercero", "cuarto", "quinto", "sexto", "séptimo", "octavo", "noveno", "décimo",
          "undécimo", "duodécimo", "decimotercero", "decimocuarto", "decimoquinto", "decimosexto",
          "decimoséptimo", "decimoctavo", "decimonoveno", "vigésimo"]


def ordinal(n, fem=False, apoc=False):
    if not 1 <= n < len(_ORD_M):
        return cardinal(n, fem)
    w = _ORD_M[n]
    if apoc and n in (1, 3):
        return w[:-1]  # primer, tercer
    return w[:-1] + "a" if fem else w


_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
_RE_ROMAN = re.compile(r"^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")


def romano(s):
    """Valor de un número romano válido en mayúsculas, o None."""
    if not s or not _RE_ROMAN.match(s):
        return None
    total = 0
    for a, b in zip(s, s[1:] + " "):
        v = _ROMAN[a]
        total += -v if _ROMAN.get(b, 0) > v else v
    return total


# ---------------------------------------------------------------- reglas

_ABREV = {
    "Sr": "señor", "Sra": "señora", "Srta": "señorita", "Sres": "señores", "Dr": "doctor", "Dra": "doctora",
    "Lic": "licenciado", "Ing": "ingeniero", "Prof": "profesor", "Profa": "profesora", "Sto": "santo",
    "Sta": "santa", "Ud": "usted", "Uds": "ustedes", "Vd": "usted", "Vds": "ustedes", "pág": "página",
    "págs": "páginas", "cap": "capítulo", "vol": "volumen", "núm": "número", "aprox": "aproximadamente",
    "tel": "teléfono", "av": "avenida", "Av": "avenida", "dpto": "departamento", "etc": "etcétera",
    "Mons": "monseñor", "Gral": "general", "Cnel": "coronel", "Cap": "capitán", "Pbro": "presbítero",
    "Excmo": "excelentísimo", "Ilmo": "ilustrísimo", "Hno": "hermano", "Hna": "hermana", "pp": "páginas",
}
_RE_ABREV = re.compile(r"(?<![\w.])(" + "|".join(sorted(map(re.escape, _ABREV), key=len, reverse=True)) + r")\.(?=\s|$|,)")

_FRASES = [
    (re.compile(r"\bp\.\s?ej\."), "por ejemplo"),
    (re.compile(r"\bEE\.\s?UU\."), "Estados Unidos"),
    (re.compile(r"\ba\.\s?C\."), "antes de Cristo"),
    (re.compile(r"\bd\.\s?C\."), "después de Cristo"),
    (re.compile(r"\ba\.\s?m\."), "de la mañana"),
    (re.compile(r"\bp\.\s?m\."), "de la tarde"),
    (re.compile(r"\bS\.\s?A\.(?=[\s,]|$)"), "sociedad anónima"),
]

_UNIDADES = {  # símbolo -> (singular, plural)
    "km": ("kilómetro", "kilómetros"), "m": ("metro", "metros"), "cm": ("centímetro", "centímetros"),
    "mm": ("milímetro", "milímetros"), "kg": ("kilogramo", "kilogramos"), "g": ("gramo", "gramos"),
    "mg": ("miligramo", "miligramos"), "l": ("litro", "litros"), "ml": ("mililitro", "mililitros"),
    "h": ("hora", "horas"), "min": ("minuto", "minutos"), "km/h": ("kilómetro por hora", "kilómetros por hora"),
    "m²": ("metro cuadrado", "metros cuadrados"), "km²": ("kilómetro cuadrado", "kilómetros cuadrados"),
    "€": ("euro", "euros"),
}
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]

_N = r"\d{1,3}(?:[.\u00a0\u202f]\d{3})+|\d+"          # 1.234.567 (puntos de millar) o 1234
_NUM = rf"(?<![\w.,])(?P<e>{_N})(?:[.,](?P<f>\d+))?"
_RE_ORD = re.compile(r"(?<![\w.,])(\d{1,3})\s?(?:\.?(º|°)|\.?(ª)|\.?(er)|\.?(os)|\.?(as))(?!\w)")
_RE_FECHA = re.compile(r"(?<![\w/.-])(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?![\w/.-])")
_RE_HORA = re.compile(r"(?<![\w:.,])(\d{1,2}):(\d{2})(?:\s?h\b\.?)?(?![\w:])")
_RE_PORC = re.compile(_NUM + r"\s?%")
_RE_GRADOS = re.compile(_NUM + r"\s?[º°]\s?([CFcf])\b")
_RE_UNIDAD = re.compile(_NUM + r"\s?(km/h|km²|m²|km|cm|mm|kg|mg|ml|min|€|g|h|m|l)(?![\w/²])")
_RE_NUMERO = re.compile(_NUM + r"(?:\s+(?P<w>[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+))?(?![\w])")
_RE_TRIGGER = re.compile(r"\b(Capítulo|Cap\.|Parte|Libro|Tomo|Acto|Escena|Volumen|Canto|Sección|Apartado|Título|"
                         r"Anexo|Tema|Lección|Fase|Etapa|Nivel|Tabla|Figura|Artículo|Art\.|siglo)\s+([IVXLCDM]+)\b")
_RE_SOBERANO = re.compile(r"\b([A-ZÁÉÍÓÚ][a-záéíóúñ]+(?:\s+(?:de|del)\s+[A-ZÁÉÍÓÚ][a-záéíóúñ]+)?)\s+([IVXLCDM]{1,6})\b")


def _fecha(m):
    d, mes, a = int(m[1]), int(m[2]), int(m[3])
    if not (1 <= d <= 31 and 1 <= mes <= 12):
        return m[0]
    dia = "primero" if d == 1 else cardinal(d)
    return f"{dia} de {_MESES[mes - 1]} de {cardinal(a)}"


def _hora(m):
    h, mi = int(m[1]), int(m[2])
    if h > 24 or mi > 59:
        return m[0]
    if mi == 0:
        return cardinal(h) if h else "cero"
    return f"{cardinal(h)} {'cero ' if mi < 10 else ''}{cardinal(mi)}"


def _ordinal(m):
    n = int(m[1])
    if m[3] or m[6]:
        return ordinal(n, fem=True)
    if m[4]:
        return ordinal(n, apoc=True)
    return ordinal(n)


def _unidad(m):
    sing, plur = _UNIDADES[m.group(3)]
    frac = m.group("f")
    uno = not frac and int(m.group("e").replace(".", "")) == 1
    return f"{_numero(m.group('e'), frac, sing)} {sing if uno else plur}"


def _general(m):
    return _numero(m.group("e"), m.group("f"), m.group("w")) + (" " + m.group("w") if m.group("w") else "")


def _romanos(texto):
    def trig(m):
        v = romano(m.group(2))
        return f"{m.group(1)} {cardinal(v)}" if v else m.group(0)

    def sob(m):
        v = romano(m.group(2))
        if not v or m.group(2) in ("L", "C", "D", "M"):
            return m.group(0)
        return f"{m.group(1)} {ordinal(v) if v <= 10 else cardinal(v)}"

    return _RE_SOBERANO.sub(sob, _RE_TRIGGER.sub(trig, texto))


def rayas(texto):
    """Rayas de diálogo («—Hola —dijo—. Adiós») a puntuación que el modelo sepa entonar."""
    texto = re.sub(r"^\s*[—–]\s*", "", texto)
    texto = re.sub(r"(?<=[?!.…])\s[—–]([^—–]+?)[—–](?=\s*[.,;:?!…])", r" \1", texto)  # ¿…? —Dijo—.
    texto = re.sub(r"\s[—–]([^—–]+?)[—–](?=\s*[.,;:?!…])", r", \1", texto)   # —aclaración— antes de signo
    texto = re.sub(r"\s[—–]([^—–]+?)[—–]\s", r", \1, ", texto)               # —aclaración— en medio
    texto = re.sub(r"([?!.…])\s*[—–]\s*", r"\1 ", texto)                      # ¿…? —dijo / … . —Dijo
    texto = re.sub(r"\s*[—–]\s*", ", ", texto)                                # cualquier otra raya
    texto = re.sub(r",\s*([,.;:?!…])", r"\1", texto)
    return re.sub(r"\s{2,}", " ", texto).strip()


def _cargar_diccionario():
    try:
        lineas = DICCIONARIO.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    pares = []
    for linea in lineas:
        if "=" in linea and not linea.lstrip().startswith("#"):
            a, _, b = linea.partition("=")
            if a.strip():
                pares.append((a.strip(), b.strip()))
    return sorted(pares, key=lambda p: -len(p[0]))


def normalizar(texto, diccionario=True):
    """Devuelve el texto tal como debe leerse en voz alta."""
    t = rayas(texto)
    for rx, rep in _FRASES:
        t = rx.sub(rep, t)
    t = re.sub(r"(?<![\w.])etc\.(?=\s+[A-ZÁÉÍÓÚ¿¡]|\s*$)", "etcétera.", t)
    t = re.sub(r"(?<![\w.])etc\.(?=\s+[a-záéíóú])", "etcétera,", t)  # «etc. dijo…» (raya de diálogo)
    t = _RE_ABREV.sub(lambda m: _ABREV[m.group(1)], t)
    t = _romanos(t)
    t = _RE_FECHA.sub(_fecha, t)
    t = _RE_HORA.sub(_hora, t)
    t = _RE_ORD.sub(_ordinal, t)
    t = _RE_GRADOS.sub(lambda m: f"{_numero(m.group('e'), m.group('f'))} grados {'centígrados' if m.group(3) in 'Cc' else 'Fahrenheit'}", t)
    t = _RE_PORC.sub(lambda m: f"{_numero(m.group('e'), m.group('f'))} por ciento", t)
    t = _RE_UNIDAD.sub(_unidad, t)
    t = _RE_NUMERO.sub(_general, t)
    t = t.replace(" & ", " y ").replace("&", " y ")
    if diccionario:
        for a, b in _cargar_diccionario():
            t = re.sub(rf"(?<!\w){re.escape(a)}(?!\w)", b, t)
    return t


if __name__ == "__main__":
    import sys
    print(normalizar(" ".join(sys.argv[1:]) or sys.stdin.read()))


# ---------------------------------------------------------------- diálogos

def slug(nombre):
    """'Doña Remedios' -> 'dona_remedios': así se escribe el nombre de un personaje tras la raya."""
    import unicodedata
    t = unicodedata.normalize("NFD", nombre.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


AVISOS = []   # personajes escritos con @ que no existen (los lee md2audio para avisar)
_PAL = r"[\wáéíóúüñÁÉÍÓÚÜÑ.-]+"


def quitar_marca(texto, validas, nombres=()):
    """Quita la marca de personaje tras la raya inicial y devuelve (texto, clave).

    '—2 Hola' -> clave 2 (número de voz); '—@marta Hola' o '—Marta: Hola' -> clave 'marta' (personaje).
    '—@legion[0] Hola' -> clave 'legion[0]': esa voz sin sus capas (sin eco ni coro), solo esta vez.
    Un número o nombre que no existe no cuenta como marca («—5 años tengo» sigue siendo texto), salvo con @,
    que siempre se quita para que no se lea en voz alta.
    """
    m = re.match(r"^(\s*[—–])\s*(\d{1,2})\s+(?=\S)", texto)
    if m and int(m.group(2)) in validas:
        return m.group(1) + texto[m.end():], int(m.group(2))
    m = re.match(rf"^(\s*[—–])\s*@({_PAL})(\[0\])?[\s:]+(?=\S)", texto)
    if m:
        clave = slug(m.group(2))
        if clave in nombres:
            return m.group(1) + texto[m.end():], clave + (m.group(3) or "")
        AVISOS.append(f"Personaje desconocido: @{m.group(2)}")
        return m.group(1) + texto[m.end():], None
    m = re.match(rf"^(\s*[—–])\s*({_PAL}(?:\s+{_PAL}){{0,2}}):\s+(?=\S)", texto)
    if m and slug(m.group(2)) in nombres:
        return m.group(1) + texto[m.end():], slug(m.group(2))
    return texto, None


def dividir_dialogo(texto, min_acotacion=0, validas=(), nombres=()):
    """Separa un párrafo con rayas en [(rol, texto, voz)] para leerlo con varias voces.

    rol es 'narrador' o 'dialogo'; voz es el número (—2 …) o el nombre (—@marta …) del personaje, o None. Un párrafo que empieza
    por raya alterna: habla del personaje, acotación del narrador («—dijo Sirio—»), habla… Toda acotación la lee
    el narrador, por corta que sea (con min_acotacion > 0, las más cortas se quedarían con la voz que hablaba).
    Un párrafo sin raya inicial es narración.
    """
    if not re.match(r"\s*[—–]", texto):
        return [("narrador", texto, None)]
    texto, voz = quitar_marca(texto, validas, nombres)
    trozos = [p.strip() for p in re.split(r"\s*[—–]\s*", texto)]
    if trozos and trozos[0] == "":
        trozos = trozos[1:]
    piezas = []   # [rol, texto]
    for i, p in enumerate(trozos):
        rol = "dialogo" if i % 2 == 0 else "narrador"
        if rol == "dialogo":
            # el signo que sigue a una acotación cerrada («—dijo Sirio—. Hoy…») pertenece a la acotación
            m = re.match(r"^([.,;:?!…]+)\s*(.*)$", p)
            if m and piezas and piezas[-1][0] == "narrador":
                piezas[-1][1] += m.group(1)
                p = m.group(2)
        if p:
            piezas.append([rol, p])
    fusion = []
    for rol, p in piezas:
        corta = rol == "narrador" and len(p) < min_acotacion
        if fusion and (corta or fusion[-1][0] == rol):
            ant = fusion[-1]
            sep = " " if ant[1][-1:] in ".?!…" else ", "
            ant[1] = f"{ant[1]}{sep}{p}"
        else:
            fusion.append([rol, p])
    return [(r, t, voz if r == "dialogo" else None) for r, t in fusion]
