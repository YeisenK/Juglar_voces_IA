#!/usr/bin/env python3
"""Juglar: lee textos en voz alta y convierte libros en audiolibros con una voz para cada personaje."""
import contextlib
import ctypes
import json
import os
import re
import signal
import subprocess
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, GObject, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

APP_ID = "io.github.yeisenk.Juglar"
ICON = "io.github.yeisenk.Juglar"
VERSION = "2.0"
WEBSITE = "https://github.com/YeisenK/Juglar"
APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))
import rutas  # noqa: E402
import cola  # noqa: E402
import md2audio  # noqa: E402  (solo para los ajustes de Qwen; no carga ningún motor)
import pruebas  # noqa: E402

CONFIG = rutas.CONFIG / "juglar.json"
VENV_PY = rutas.VENV_PY
MD2AUDIO = APP_DIR / "md2audio.py"
DICCIONARIO = rutas.DICCIONARIO
ESTILO = APP_DIR / "estilo.css"
QWEN_PY = rutas.QWEN_PY
CREAR_VOZ = rutas.MOTORES / "crear_voz.py"
TEXT_EXTS = (".md", ".markdown", ".mdx", ".txt")
AUDIO_EXTS = (".mp3", ".ogg", ".opus", ".m4a", ".m4b", ".wav")
FORMATS = ["mp3", "ogg", "m4b", "wav"]
WORDS_PER_MIN = 150  # ritmo aproximado de narración a velocidad 1×
_libc = ctypes.CDLL(None, use_errno=True)


def die_with_app():
    """Para preexec_fn: el hijo recibe SIGTERM si la app termina (aunque sea por un cierre brusco)."""
    _libc.prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG


def fmt_time(sec):
    sec = int(sec or 0)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def timecode(sec):
    sec = int(sec or 0)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


# ---------------------------------------------------------------- voces

def list_voices():
    """{voz: frecuencia} de todos los motores, según md2audio."""
    try:
        out = subprocess.run([str(VENV_PY), "-I", str(MD2AUDIO), "--list-voices"],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    return {v: int(r) for v, r in (line.split("\t") for line in out.splitlines() if "\t" in line)}


REGIONS = {"es_ES": "España", "es_MX": "México", "es_AR": "Argentina", "es_US": "EE. UU.", "es_CO": "Colombia"}
QWEN_LABELS = {
    "narradora": "Narradora de audiolibros",
    "narrador": "Narrador de audiolibros",
    "narradora_espana": "Narradora española",
    "documental_mujer": "Narradora de documentales",
    "documental_hombre": "Narrador de documentales",
}


def qwen_name(spec):
    return spec.split(":", 1)[1] if spec and spec.startswith("qwen:") else None


def short_label(spec):
    """Nombre de la voz sin el motor: «Narrador de audiolibros», «Dora (mujer)»…"""
    if spec.startswith("qwen:"):
        name = spec.split(":", 1)[1]
        return QWEN_LABELS.get(name) or md2audio._json(md2audio.QWEN_VOICES / name / "meta.json").get("label") \
            or name.replace("_", " ").capitalize()
    if spec.startswith("kokoro:"):
        name = spec.split(":", 1)[1]
        gender = {"f": "mujer", "m": "hombre"}.get(name[1:2], "")
        return f"{name[3:].capitalize()} ({gender})"
    region, _, rest = spec.partition("-")
    name, _, quality = rest.partition("-")
    return f"{name.capitalize()} ({REGIONS.get(region, region)}, {quality.replace('_', ' ')})"


def engine_of(spec):
    return "Qwen" if spec.startswith("qwen:") else "Kokoro" if spec.startswith("kokoro:") else "Piper"


def voice_label(spec):
    return f"{engine_of(spec)} · {short_label(spec)}"


# ---------------------------------------------------------------- ajustes en disco

def load_config():
    try:
        return json.loads(CONFIG.read_text())
    except Exception:
        return {}


def save_config(data):
    try:
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(data))
    except Exception:
        pass


def write_json(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
        os.replace(tmp, path)
    except OSError:
        pass


def load_elenco():
    return md2audio.elenco()


def save_elenco(elenco):
    write_json(md2audio.ELENCO, elenco)


def save_voice_settings(name, values):
    """ajustes.json de la voz: solo el muestreo que difiere de fábrica."""
    path = md2audio.QWEN_VOICES / name / "ajustes.json"
    diff = {k: values[k] for k in md2audio.VOICE_KEYS if values[k] != md2audio.QWEN_DEFAULTS[k]}
    if diff:
        write_json(path, diff)
    else:
        path.unlink(missing_ok=True)


def save_libro(values):
    """libro.json: ajustes comunes a todas las voces, solo lo que difiere de fábrica."""
    diff = {k: v for k, v in values.items() if md2audio.QWEN_DEFAULTS.get(k) != v}
    if diff:
        write_json(md2audio.LIBRO_FILE, diff)
    else:
        md2audio.LIBRO_FILE.unlink(missing_ok=True)


ESTILOS = [  # (nombre, muestreo); «Personalizado» es cualquier otra combinación
    ("Estable", {"temperature": 0.6, "top_p": 0.9, "top_k": 30, "repetition_penalty": 1.05}),
    ("Equilibrado", {"temperature": 0.75, "top_p": 0.95, "top_k": 50, "repetition_penalty": 1.05}),
    ("Expresivo", {"temperature": 0.9, "top_p": 1.0, "top_k": 50, "repetition_penalty": 1.05}),
]


def style_index(values):
    for i, (_n, v) in enumerate(ESTILOS):
        if all(abs(float(values[k]) - x) < 1e-6 for k, x in v.items()):
            return i
    return len(ESTILOS)


# ---------------------------------------------------------------- widgets auxiliares

def label(text="", css=(), **kw):
    w = Gtk.Label(label=text, **kw)
    for c in (css if isinstance(css, (list, tuple)) else [css]):
        w.add_css_class(c)
    return w


def tool_button(icon, text, tip, cb, css=()):
    """Botón compacto de barra de herramientas: icono + texto."""
    b = Gtk.Button(child=Adw.ButtonContent(icon_name=icon, label=text), tooltip_text=tip)
    for c in (css if isinstance(css, (list, tuple)) else [css]):
        b.add_css_class(c)
    b.connect("clicked", cb)
    return b


def strip(title):
    """Franja de cabecera de panel con el título en versalitas; devuelve (franja, caja de la derecha)."""
    box = Gtk.Box(spacing=8)
    box.add_css_class("strip")
    box.append(label(title.upper(), "panel-title", xalign=0, valign=Gtk.Align.CENTER))
    right = Gtk.Box(spacing=6, hexpand=True, halign=Gtk.Align.END)
    box.append(right)
    return box, right


def field(name, widget):
    """Campo de barra de herramientas: etiqueta pequeña + control."""
    box = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
    box.append(label(name.upper(), "field-label", valign=Gtk.Align.CENTER))
    box.append(widget)
    return box


def scale_row(title, subtitle, lo, hi, step, fmt):
    """Fila con título y deslizador; devuelve (fila, escala)."""
    row = Adw.ActionRow(title=title, subtitle=subtitle)
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
    scale.set_size_request(200, -1)
    scale.set_valign(Gtk.Align.CENTER)
    scale.set_draw_value(True)
    scale.set_value_pos(Gtk.PositionType.RIGHT)
    scale.set_format_value_func(lambda _s, v: fmt(v))
    row.add_suffix(scale)
    return row, scale


class SoundControls:
    """Estilo, temperatura y ajustes avanzados (y velocidad, si speed) de una voz o de un personaje."""

    def __init__(self, title, description, on_change, speed=False):
        self.on_change, self.loading = on_change, False
        self.group = Adw.PreferencesGroup(title=title, description=description)
        self.style_row = Adw.ComboRow(title="Estilo", subtitle="Atajos para la temperatura y el muestreo",
                                      model=Gtk.StringList.new([n for n, _ in ESTILOS] + ["Personalizado"]))
        self.group.add(self.style_row)
        row, self.temp = scale_row("Temperatura", "Baja: más uniforme y estable · Alta: más expresiva y variable",
                                   0.3, 1.3, 0.05, lambda v: f"{v:.2f}")
        self.group.add(row)
        adv = Adw.ExpanderRow(title="Ajustes avanzados", subtitle="Muestreo del modelo")
        row, self.topp = scale_row("Top P", "Cuánta probabilidad se considera (menos = más conservador)",
                                   0.5, 1.0, 0.01, lambda v: f"{v:.2f}")
        adv.add_row(row)
        self.topk = Adw.SpinRow(title="Top K", subtitle="Cuántas opciones se barajan en cada paso",
                                adjustment=Gtk.Adjustment(value=50, lower=5, upper=100, step_increment=5))
        adv.add_row(self.topk)
        row, self.rep = scale_row("Penalización por repetir", "Evita tonos o sílabas repetidas",
                                  1.0, 1.5, 0.01, lambda v: f"{v:.2f}")
        adv.add_row(row)
        self.group.add(adv)
        self.speed = None
        if speed:
            row, self.speed = scale_row("Velocidad", "Más lento para un anciano, más rápido para un niño",
                                        0.6, 1.4, 0.05, lambda v: f"{v:.2f}×")
            self.group.add(row)
        self.style_row.connect("notify::selected", self._changed)
        for w in (self.temp, self.topp, self.rep) + ((self.speed,) if speed else ()):
            w.connect("value-changed", self._changed)
        self.topk.connect("notify::value", self._changed)

    def values(self):
        v = {"temperature": round(self.temp.get_value(), 2), "top_p": round(self.topp.get_value(), 2),
             "top_k": int(self.topk.get_value()), "repetition_penalty": round(self.rep.get_value(), 2)}
        if self.speed:
            v["velocidad"] = round(self.speed.get_value(), 2)
        return v

    def load(self, cfg):
        was, self.loading = self.loading, True
        self.temp.set_value(cfg["temperature"])
        self.topp.set_value(cfg["top_p"])
        self.topk.set_value(cfg["top_k"])
        self.rep.set_value(cfg["repetition_penalty"])
        if self.speed:
            self.speed.set_value(cfg.get("velocidad", 1.0))
        self.style_row.set_selected(style_index(cfg))
        self.loading = was

    def _changed(self, widget, *_):
        if self.loading:
            return
        self.loading = True
        i = self.style_row.get_selected()
        if widget is self.style_row and i < len(ESTILOS):
            v = ESTILOS[i][1]
            self.temp.set_value(v["temperature"])
            self.topp.set_value(v["top_p"])
            self.topk.set_value(v["top_k"])
            self.rep.set_value(v["repetition_penalty"])
        elif widget is not self.style_row:
            self.style_row.set_selected(style_index(self.values()))
        self.loading = False
        self.on_change()


class JobRow:
    """Fila de la cola, en columnas: estado · archivo · voz · progreso · tiempo · acciones."""

    STATE_ICONS = {"queued": "content-loading-symbolic", "running": "media-record-symbolic",
                   "done": "emblem-ok-symbolic", "failed": "dialog-warning-symbolic",
                   "cancelled": "action-unavailable-symbolic"}

    def __init__(self, win, job_id):
        self.win, self.job_id, self.out = win, job_id, None
        self.box = Gtk.Box(spacing=12, margin_top=9, margin_bottom=9, margin_start=12, margin_end=8)
        self.icon = Gtk.Image(pixel_size=16, valign=Gtk.Align.CENTER)
        self.icon.add_css_class("state")
        win.cols["estado"].add_widget(self.icon)
        self.box.append(self.icon)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True, valign=Gtk.Align.CENTER)
        self.title = label("", "job-title", xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE)
        self.sub = label("", "job-sub", xalign=0, ellipsize=Pango.EllipsizeMode.END)
        info.append(self.title)
        info.append(self.sub)
        self.box.append(info)
        self.voice = label("", "job-cell", xalign=0, ellipsize=Pango.EllipsizeMode.END, width_chars=18,
                           max_width_chars=18)
        win.cols["voz"].add_widget(self.voice)
        self.box.append(self.voice)
        prog = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        self.bar = Gtk.ProgressBar(valign=Gtk.Align.CENTER, width_request=110)
        self.pct = label("", "job-cell", xalign=1, width_chars=5)
        prog.append(self.bar)
        prog.append(self.pct)
        win.cols["progreso"].add_widget(prog)
        self.box.append(prog)
        self.time = label("", "job-cell", xalign=1, width_chars=8)
        win.cols["tiempo"].add_widget(self.time)
        self.box.append(self.time)
        actions = Gtk.Box(spacing=2, valign=Gtk.Align.CENTER)
        self.play = self._btn("media-playback-start-symbolic", "Escuchar", lambda *_: win.launch(self.out))
        self.folder = self._btn("folder-open-symbolic", "Abrir carpeta", lambda *_: win.launch(self.out, folder=True))
        self.cancel = self._btn("process-stop-symbolic", "Cancelar",
                                lambda *_: (cola.cancel_job(job_id), win.refresh_queue()))
        self.remove = self._btn("edit-delete-symbolic", "Quitar de la lista",
                                lambda *_: (cola.remove_job(job_id), win.refresh_queue()))
        for w in (self.play, self.folder, self.cancel, self.remove):
            actions.append(w)
        win.cols["acciones"].add_widget(actions)
        self.box.append(actions)
        self.row = Gtk.ListBoxRow(child=self.box, activatable=False)

    @staticmethod
    def _btn(icon, tip, cb):
        b = Gtk.Button(icon_name=icon, tooltip_text=tip)
        b.add_css_class("flat")
        b.connect("clicked", cb)
        return b

    def update(self, job, paused):
        st = job["status"]
        self.out = Path(job["out"])
        for s in ("done", "failed", "running"):
            self.row.remove_css_class(f"job-{s}")
        if st in ("done", "failed", "running"):
            self.row.add_css_class(f"job-{st}")
        self.icon.set_from_icon_name("media-playback-pause-symbolic" if st == "running" and paused
                                     else self.STATE_ICONS.get(st, "audio-x-generic-symbolic"))
        self.title.set_label(job["title"])
        self.voice.set_label(short_label(job["voice"]))
        self.voice.set_tooltip_text(voice_label(job["voice"]))
        frac = job["done"] / max(job["total"], 1) if st == "running" else 1.0 if st == "done" else 0.0
        self.bar.set_fraction(frac)
        self.pct.set_label(f"{frac * 100:.0f} %" if st in ("running", "done") else "—")
        if st == "queued":
            sub, t = f"En cola → {self.out.name}", "—"
        elif st == "running":
            eta = job.get("eta")
            if paused:
                sub = "En pausa"
            elif job["total"] == 0:
                sub = "Preparando la voz…"
            elif frac >= 1:
                sub = "Añadiendo capítulos…"
            else:
                sub = f"Convirtiendo → {self.out.name}"
            t = f"−{fmt_time(eta)}" if eta and frac < 1 and not paused else "…"
        elif st == "done":
            extra = f" · {job['chapters']} capítulos" if job.get("chapters") else ""
            rev = job.get("revision")
            if rev:
                extra += f" · revisado ({rev['regenerados']} regenerados" + (
                    f", {rev['sin_arreglar']} dudosos)" if rev["sin_arreglar"] else ")")
            sub, t = f"{self.out}{extra}", fmt_time(job.get("duration"))
        else:
            sub = job.get("message") or ("Cancelado" if st == "cancelled" else "No se pudo convertir")
            t = "—"
        self.sub.set_label(sub)
        self.sub.set_tooltip_text(sub)
        self.time.set_label(t)
        self.play.set_visible(st == "done")
        self.folder.set_visible(st == "done")
        self.cancel.set_visible(st in ("queued", "running"))
        self.remove.set_visible(st != "running")


# ---------------------------------------------------------------- ventana

PAGES = [  # (nombre, título, icono)
    ("leer", "Leer", "media-playback-start-symbolic"),
    ("cola", "Exportar", "document-send-symbolic"),
    ("voces", "Voces", "audio-input-microphone-symbolic"),
    ("ajustes", "Audiolibro", "emblem-system-symbolic"),
]


class JuglarWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Juglar")
        self.set_default_size(1180, 760)
        self.set_size_request(560, 500)
        self.proc = None
        self.read_paused = False
        self.loading = True          # mientras se montan los widgets no se guarda nada
        self.cfg = load_config()
        self.rates = list_voices()
        orden = ("Qwen", "Kokoro", "Piper")
        self.voices = sorted(self.rates, key=lambda v: orden.index(engine_of(v)))
        self.sel_voice = None        # voz o personaje abierto en la página Voces
        self.sel_char = None
        self.syncing = False
        self.entry_specs = []
        self.rows = {}
        self.queue_mtime = None
        self.doc_name = None
        self.stats_source = None
        self.generating = set()      # pruebas de voz que se están generando ahora
        self.preview_spec = None     # voz o personaje cuya prueba está sonando
        self.dirty_spec = None       # voz o personaje con ajustes cambiados y sin guardar
        self.cols = {k: Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
                     for k in ("estado", "voz", "progreso", "tiempo", "acciones")}

        # estado compartido entre páginas: narrador, velocidad, formato
        self.voice_model = Gtk.StringList.new([voice_label(v) for v in self.voices])
        self.speed_adj = Gtk.Adjustment(value=self.cfg.get("speed", 1.0), lower=0.5, upper=2.0,
                                        step_increment=0.05, page_increment=0.25)
        self.format_model = Gtk.StringList.new(FORMATS)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120,
                               hexpand=True, vexpand=True)
        builders = {"leer": self.build_read_page, "cola": self.build_queue_page,
                    "voces": self.build_voices_page, "ajustes": self.build_settings_page}
        for name, _t, _i in PAGES:
            self.stack.add_named(builders[name](), name)

        # barra lateral de herramientas
        rail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        rail.add_css_class("rail")
        brand = Gtk.Image(icon_name=ICON, pixel_size=30, tooltip_text=f"Juglar {VERSION}")
        brand.add_css_class("brand")
        rail.append(brand)
        self.rail_buttons, group = {}, None
        for i, (name, title, icon) in enumerate(PAGES):
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            inner.append(Gtk.Image(icon_name=icon, pixel_size=20))
            inner.append(label(title, "rail-label"))
            b = Gtk.ToggleButton(child=inner, tooltip_text=f"{title} (Ctrl+{i + 1})")
            if group:
                b.set_group(group)
            group = group or b
            b.connect("toggled", lambda btn, n=name: btn.get_active() and self.stack.set_visible_child_name(n))
            rail.append(b)
            self.rail_buttons[name] = b
        self.stack.connect("notify::visible-child-name", self.on_page_changed)

        body = Gtk.Box()
        body.append(rail)
        body.append(self.stack)

        self.win_title = Adw.WindowTitle(title="Juglar", subtitle="")
        header = Adw.HeaderBar(title_widget=self.win_title)
        # aviso siempre visible mientras el modo flash está activo; al pulsarlo se apaga
        self.flash_badge = Gtk.Button(child=Adw.ButtonContent(icon_name="weather-storm-symbolic",
                                                              label="Modo flash activado"),
                                      tooltip_text="Sin revisar con Whisper y todo con la voz del narrador.\n"
                                                   "Pulsa para desactivarlo.", visible=False)
        self.flash_badge.add_css_class("flash-badge")
        self.flash_badge.connect("clicked", lambda *_: self.libro_widgets["flash"].set_active(False))
        header.pack_start(self.flash_badge)
        menu = Gio.Menu()
        menu.append("Atajos de teclado", "win.atajos")
        menu.append("Abrir carpeta de voces", "win.carpeta-voces")
        menu.append("Acerca de Juglar", "win.acerca")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu, tooltip_text="Menú"))
        for name, cb in (("atajos", self.on_shortcuts), ("acerca", self.on_about),
                         ("carpeta-voces", lambda *_: self.launch(md2audio.QWEN_VOICES))):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", cb)
            self.add_action(act)

        toolbar = Adw.ToolbarView(content=body)
        toolbar.add_top_bar(header)
        toolbar.add_bottom_bar(self.build_statusbar())
        self.toasts = Adw.ToastOverlay(child=toolbar)
        self.set_content(self.toasts)

        # ventanas medianas: sin inspector; estrechas: además, la lista de voces pasa a un desplegable
        medium = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 980sp"))
        medium.add_setter(self.inspector, "visible", GObject.Value(bool, False))
        small = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 760sp"))
        small.add_setter(self.inspector, "visible", GObject.Value(bool, False))
        small.add_setter(self.voice_side, "visible", GObject.Value(bool, False))
        small.add_setter(self.voice_pick, "visible", GObject.Value(bool, True))
        self.add_breakpoint(medium)
        self.add_breakpoint(small)

        drop = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop.connect("drop", self.on_drop)
        drop.connect("enter", lambda *_: (self.dropzone.add_css_class("hover"), Gdk.DragAction.COPY)[1])
        drop.connect("leave", lambda *_: self.dropzone.remove_css_class("hover"))
        self.add_controller(drop)

        keys = Gtk.ShortcutController()
        shortcuts = [("<Control>Return", lambda: self.on_play_clicked(None)), ("Escape", self.stop),
                     ("<Control>o", lambda: self.on_read_file(None)),
                     ("<Control>s", lambda: self.save_changes()),
                     ("<Control><Shift>e", lambda: self.on_export_text(None))]
        shortcuts += [(f"<Control>{i + 1}", lambda n=name: self.stack.set_visible_child_name(n))
                      for i, (name, _t, _i) in enumerate(PAGES)]
        for trigger, cb in shortcuts:
            keys.add_shortcut(Gtk.Shortcut.new(Gtk.ShortcutTrigger.parse_string(trigger),
                                               Gtk.CallbackAction.new(lambda *_a, f=cb: (f(), True)[1])))
        self.add_controller(keys)
        self.connect("close-request", self.on_close)

        # voz inicial y datos de cada página
        if self.cfg.get("voice") in self.voices:
            self.voice_dd.set_selected(self.voices.index(self.cfg["voice"]))
        if self.cfg.get("audio_ext") in FORMATS:
            self.format_row.set_selected(FORMATS.index(self.cfg["audio_ext"]))
        page = self.cfg.get("page") if self.cfg.get("page") in builders else "leer"
        self.stack.set_visible_child_name(page)
        self.on_page_changed()
        self.fill_voice_list()
        self.load_libro_ui()
        self.refresh_queue()
        self.update_stats()
        self.update_statusbar_voice()
        q = cola.snapshot()
        if cola.has_work(q) and not q["paused"]:
            cola.ensure_daemon()  # quedó trabajo pendiente de antes (p. ej. tras reiniciar)
        GLib.timeout_add(1000, self.poll_queue)
        self.loading = False
        if not self.voices:
            self.toast("No se encontró ninguna voz instalada")

    def on_page_changed(self, *_):
        name = self.stack.get_visible_child_name()
        if name in self.rail_buttons and not self.rail_buttons[name].get_active():
            self.rail_buttons[name].set_active(True)
        sub = {"leer": self.doc_name or "Texto sin guardar", "cola": "Cola de exportación",
               "voces": "Voces y personajes", "ajustes": "Ajustes del audiolibro"}.get(name, "")
        self.win_title.set_subtitle(sub)

    # ------------------------------------------------------------ barra de estado
    def build_statusbar(self):
        bar = Gtk.Box(spacing=10)
        bar.add_css_class("statusbar")
        self.sb_dot = Gtk.Box(valign=Gtk.Align.CENTER)
        self.sb_dot.add_css_class("status-dot")
        self.sb_dot.add_css_class("ok")
        bar.append(self.sb_dot)
        self.sb_text = label("Listo", xalign=0, ellipsize=Pango.EllipsizeMode.END)
        bar.append(self.sb_text)
        bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.sb_queue = label("", xalign=0, ellipsize=Pango.EllipsizeMode.END, hexpand=True)
        bar.append(self.sb_queue)
        self.sb_voice = label("", xalign=1, ellipsize=Pango.EllipsizeMode.START)
        bar.append(self.sb_voice)
        return bar

    def set_status(self, text, state="ok"):
        self.sb_text.set_label(text)
        for s in ("ok", "busy", "paused"):
            self.sb_dot.remove_css_class(s)
        self.sb_dot.add_css_class(state)

    def update_statusbar_voice(self):
        v = self.current_voice()
        self.sb_voice.set_label(f"Narrador: {voice_label(v)}  ·  {self.speed_adj.get_value():.2f}×" if v else "")

    # ------------------------------------------------------------ página: Leer
    def build_read_page(self):
        root = Gtk.Box()
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)

        head, right = strip("Documento")
        self.doc_label = label("Texto sin guardar", "job-sub", xalign=0, hexpand=True,
                               ellipsize=Pango.EllipsizeMode.MIDDLE, margin_start=6)
        head.insert_child_after(self.doc_label, head.get_first_child())
        right.set_hexpand(False)
        for icon, text, tip, cb in (
                ("document-open-symbolic", "Abrir", "Abrir un .md o .txt y leerlo (Ctrl+O)", self.on_read_file),
                ("edit-paste-symbolic", "Pegar y leer", "Pegar el portapapeles y leerlo", self.on_paste_read),
                ("edit-clear-all-symbolic", "Borrar", "Borrar el texto", self.on_clear_text)):
            right.append(tool_button(icon, text, tip, cb, "flat"))
        left.append(head)

        self.textview = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=22, bottom_margin=22,
                                     left_margin=28, right_margin=28, pixels_below_lines=6, pixels_inside_wrap=3)
        self.textview.add_css_class("editor")
        self.buffer = self.textview.get_buffer()
        self.buffer.set_text(self.cfg.get("text", ""))
        hint = label("Escribe o pega aquí el texto que quieres escuchar,\no abre un archivo .md o .txt (Ctrl+O).",
                     "hint", justify=Gtk.Justification.CENTER, can_target=False, halign=Gtk.Align.CENTER,
                     valign=Gtk.Align.CENTER)
        self.buffer.connect("changed", lambda b: (hint.set_visible(b.get_char_count() == 0), self.queue_stats()))
        hint.set_visible(self.buffer.get_char_count() == 0)
        scroller = Gtk.ScrolledWindow(vexpand=True, child=self.textview)
        scroller.add_css_class("editor-frame")
        overlay = Gtk.Overlay(child=scroller, vexpand=True)
        overlay.add_overlay(hint)
        left.append(overlay)

        # transporte: controles y tiempo a la izquierda, voz y velocidad a la derecha (se reparten si no caben)
        transport = Adw.WrapBox(child_spacing=18, line_spacing=8, justify=Adw.JustifyMode.NONE)
        transport.add_css_class("transport")
        ctrls = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        self.stop_btn = Gtk.Button(icon_name="media-playback-stop-symbolic", tooltip_text="Detener (Esc)",
                                   sensitive=False, valign=Gtk.Align.CENTER)
        self.stop_btn.add_css_class("ctrl")
        self.stop_btn.connect("clicked", lambda *_: self.stop())
        self.play_btn = Gtk.Button(icon_name="media-playback-start-symbolic", tooltip_text="Leer (Ctrl+Intro)",
                                   valign=Gtk.Align.CENTER)
        self.play_btn.add_css_class("suggested-action")
        self.play_btn.add_css_class("play")
        self.play_btn.connect("clicked", self.on_play_clicked)
        ctrls.append(self.stop_btn)
        ctrls.append(self.play_btn)
        self.timecode = label("00:00:00", "timecode", valign=Gtk.Align.CENTER)
        ctrls.append(self.timecode)
        self.read_status = label("Listo", "transport-status", xalign=0, valign=Gtk.Align.CENTER,
                                 ellipsize=Pango.EllipsizeMode.END, width_chars=16)
        ctrls.append(self.read_status)
        transport.append(ctrls)

        self.voice_dd = Gtk.DropDown(model=self.voice_model, tooltip_text="Voz del narrador", enable_search=True,
                                     width_request=250, valign=Gtk.Align.CENTER)
        self.voice_dd.connect("notify::selected", self.on_narrator_changed)
        transport.append(field("Voz", self.voice_dd))
        speed = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.speed_adj, width_request=190,
                          draw_value=True, value_pos=Gtk.PositionType.RIGHT, valign=Gtk.Align.CENTER,
                          tooltip_text="Velocidad de lectura")
        speed.set_format_value_func(lambda _s, v: f"{v:.2f}×")
        speed.add_mark(1.0, Gtk.PositionType.BOTTOM, None)
        self.speed_adj.connect("value-changed", lambda *_: (self.update_statusbar_voice(), self.update_stats()))
        transport.append(field("Velocidad", speed))
        left.append(transport)
        root.append(left)

        # inspector: datos del documento, reparto y exportación
        self.inspector = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, width_request=290)
        self.inspector.add_css_class("inspector")
        ins_head, _ = strip("Propiedades")
        self.inspector.append(ins_head)
        scroller = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scroller.set_child(col)
        self.inspector.append(scroller)

        sec = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sec.add_css_class("section")
        sec.append(label("DOCUMENTO", "stat-label", xalign=0))
        grid = Gtk.Grid(column_spacing=18, row_spacing=10, column_homogeneous=True)
        self.stats = {}
        for i, (key, name) in enumerate((("palabras", "PALABRAS"), ("duracion", "DURACIÓN APROX."),
                                         ("parrafos", "PÁRRAFOS"), ("caracteres", "CARACTERES"))):
            cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            self.stats[key] = label("0", "stat-value", xalign=0)
            cell.append(self.stats[key])
            cell.append(label(name, "stat-label", xalign=0))
            grid.attach(cell, i % 2, i // 2, 1, 1)
        sec.append(grid)
        col.append(sec)

        sec = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sec.add_css_class("section")
        sec.append(label("REPARTO EN EL TEXTO", "stat-label", xalign=0))
        self.cast_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sec.append(self.cast_box)
        col.append(sec)

        sec = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sec.add_css_class("section")
        sec.append(label("EXPORTAR", "stat-label", xalign=0))
        self.export_fmt = Gtk.DropDown(model=self.format_model, hexpand=True)
        sec.append(field("Formato", self.export_fmt))
        export = Gtk.Button(child=Adw.ButtonContent(icon_name="document-send-symbolic", label="Exportar a audio…"),
                            tooltip_text="Guardar este texto como audio (Ctrl+Mayús+E)")
        export.add_css_class("suggested-action")
        export.connect("clicked", self.on_export_text)
        sec.append(export)
        sec.append(label("Se añade a la cola de exportación y se convierte en segundo plano.", "job-sub",
                         xalign=0, wrap=True))
        col.append(sec)
        root.append(self.inspector)
        return root

    def on_clear_text(self, _btn):
        self.buffer.set_text("")
        self.doc_name = None
        self.doc_label.set_label("Texto sin guardar")
        self.on_page_changed()

    def queue_stats(self):
        """Recalcula los datos del documento poco después de dejar de escribir."""
        if self.stats_source:
            GLib.source_remove(self.stats_source)
        self.stats_source = GLib.timeout_add(350, self.update_stats)

    def update_stats(self):
        self.stats_source = None
        text = self.get_text()
        words = len(re.findall(r"\w+", text))
        mins = words / WORDS_PER_MIN / max(self.speed_adj.get_value(), 0.1)
        self.stats["palabras"].set_label(f"{words:,}".replace(",", "."))
        self.stats["caracteres"].set_label(f"{len(text):,}".replace(",", "."))
        self.stats["parrafos"].set_label(str(len([p for p in re.split(r"\n\s*\n", text) if p.strip()])))
        self.stats["duracion"].set_label(fmt_time(mins * 60) if words else "0:00")
        self.update_cast(text)
        return False

    def update_cast(self, text):
        """Quién habla en el texto: marcas —@nombre, —N y rayas sin marca, con la voz que les toca."""
        while (c := self.cast_box.get_first_child()) is not None:
            self.cast_box.remove(c)
        cast, mapa = load_elenco(), md2audio.personajes()
        nombres, numeros, sin_marca = {}, {}, 0
        for line in text.splitlines():
            m = re.match(r"^\s*[—–]\s*(.*)", line)
            if not m:
                continue
            resto = m.group(1)
            if (n := re.match(r"@([\wáéíóúüñÁÉÍÓÚÜÑ.-]+)", resto)):
                key = md2audio.texto_es.slug(n.group(1))
                nombres[key] = nombres.get(key, 0) + 1
            elif (n := re.match(r"(\d{1,2})\s", resto)) and int(n.group(1)) in mapa:
                numeros[int(n.group(1))] = numeros.get(int(n.group(1)), 0) + 1
            else:
                sin_marca += 1
        lines = []
        for key, count in sorted(nombres.items()):
            ficha = cast.get(key)
            if ficha:
                base = short_label("qwen:" + ficha["voz"])
                desc = ficha["nombre"] if base == ficha["nombre"] else f"{ficha['nombre']} · voz {base}"
                lines.append((f"—@{key}", desc, count, False))
            else:
                lines.append((f"—@{key}", "no existe: créalo en Voces", count, True))
        for num, count in sorted(numeros.items()):
            lines.append((f"—{num}", short_label("qwen:" + mapa[num]), count, False))
        if sin_marca:
            dialog = md2audio.libro_settings().get("voz_dialogo")
            lines.append(("—", "Voz de los diálogos: " + (short_label("qwen:" + dialog) if dialog else "la del narrador"),
                          sin_marca, False))
        if not lines:
            self.cast_box.append(label("Sin diálogos con raya. Todo lo lee el narrador.", "job-sub",
                                       xalign=0, wrap=True))
            return
        for chip, desc, count, warn in lines:
            row = Gtk.Box(spacing=8)
            row.append(label(chip, ["chip", "accent"] if not warn else "chip", valign=Gtk.Align.CENTER))
            row.append(label(desc, ["cast-line"] + (["warn"] if warn else []), xalign=0, hexpand=True,
                             ellipsize=Pango.EllipsizeMode.END, tooltip_text=desc))
            row.append(label(f"×{count}", "job-cell"))
            self.cast_box.append(row)

    def on_export_text(self, _btn):
        text = self.get_text()
        if not text or not self.current_voice():
            self.toast("No hay texto o voz")
            return
        ext = FORMATS[self.export_fmt.get_selected()]
        stem = Path(self.doc_name).stem if self.doc_name else "lectura"
        dialog = Gtk.FileDialog(title="Exportar a audio", initial_name=f"{stem}.{ext}")
        if self.cfg.get("last_dir") and Path(self.cfg["last_dir"]).is_dir():
            dialog.set_initial_folder(Gio.File.new_for_path(self.cfg["last_dir"]))
        dialog.save(self, None, self._export_done, text)

    def _export_done(self, dialog, res, text):
        try:
            out = Path(dialog.save_finish(res).get_path())
        except GLib.Error:
            return
        if out.suffix.lower() not in AUDIO_EXTS:
            out = out.with_name(out.name + "." + FORMATS[self.export_fmt.get_selected()])
        cola.add_job(None, out, self.current_voice(), round(self.speed_adj.get_value(), 3),
                     text=text, title=self.doc_name or f"Texto: {out.name}", overwrite=True)
        self.toast(f"Exportando «{out.name}» en la cola")
        self.refresh_queue()

    # ------------------------------------------------------------ página: Exportar (cola)
    def build_queue_page(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        head, right = strip("Cola de exportación")
        self.pause_btn = Gtk.Button()
        self.pause_btn.connect("clicked", self.on_pause_clicked)
        self.clear_btn = tool_button("edit-clear-all-symbolic", "Quitar terminados", "Quitar de la lista lo terminado",
                                     lambda *_: (cola.clear_finished(), self.refresh_queue()), "flat")
        right.append(self.clear_btn)
        right.append(self.pause_btn)
        right.append(tool_button("list-add-symbolic", "Añadir archivos", "Añadir .md o .txt a la cola",
                                 self.on_convert, "suggested-action"))
        root.append(head)

        # ajustes para los trabajos nuevos
        opts = Adw.WrapBox(child_spacing=18, line_spacing=6)
        opts.add_css_class("strip")
        self.queue_voice = Gtk.DropDown(model=self.voice_model, enable_search=True, width_request=250)
        self.voice_dd.bind_property("selected", self.queue_voice, "selected",
                                    GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        opts.append(field("Narrador", self.queue_voice))
        self.format_row = Gtk.DropDown(model=self.format_model)
        self.format_row.bind_property("selected", self.export_fmt, "selected",
                                      GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        opts.append(field("Formato", self.format_row))
        spin = Gtk.SpinButton(adjustment=self.speed_adj, digits=2, width_chars=4)
        opts.append(field("Velocidad", spin))
        root.append(opts)

        cols = Gtk.Box(spacing=12)
        cols.add_css_class("col-head")
        for key, text, kw in (("estado", "", {}), (None, "ARCHIVO", {"hexpand": True}), ("voz", "VOZ", {}),
                              ("progreso", "PROGRESO", {}), ("tiempo", "TIEMPO", {"xalign": 1}),
                              ("acciones", "", {})):
            w = label(text, xalign=kw.pop("xalign", 0), **kw)
            if key:
                self.cols[key].add_widget(w)
            cols.append(w)
        self.col_head = cols

        self.job_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.job_list.add_css_class("joblist")
        listing = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        listing.append(cols)
        listing.append(Gtk.ScrolledWindow(child=self.job_list, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER))

        self.dropzone = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, valign=Gtk.Align.CENTER,
                                halign=Gtk.Align.CENTER)
        self.dropzone.add_css_class("dropzone")
        self.dropzone.append(Gtk.Image(icon_name="document-send-symbolic", pixel_size=48, css_classes=["dim-label"]))
        self.dropzone.append(label("Suelta aquí archivos .md o .txt", "title"))
        self.dropzone.append(label("Se convierten en audio uno tras otro, en segundo plano,\n"
                                   "aunque cierres la ventana o el equipo esté en reposo.", "desc",
                                   justify=Gtk.Justification.CENTER))
        pick = Gtk.Button(label="Elegir archivos…", halign=Gtk.Align.CENTER, margin_top=6)
        pick.add_css_class("suggested-action")
        pick.add_css_class("pill")
        pick.connect("clicked", self.on_convert)
        self.dropzone.append(pick)

        self.queue_stack = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.queue_stack.add_named(self.dropzone, "vacio")
        self.queue_stack.add_named(listing, "lista")
        root.append(self.queue_stack)
        return root

    # ------------------------------------------------------------ página: Voces y personajes
    def build_voices_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        head, right = strip("Voces y personajes")
        self.create_spinner = Gtk.Spinner()
        self.create_status = label("", "job-sub", ellipsize=Pango.EllipsizeMode.END)
        right.append(self.create_spinner)
        right.append(self.create_status)
        right.append(tool_button("list-add-symbolic", "Nuevo personaje",
                                 "Un personaje es una voz con su nombre y sus ajustes guardados",
                                 self.on_new_character, "flat"))
        self.unsaved_label = label("● Cambios sin guardar", "unsaved", visible=False, valign=Gtk.Align.CENTER)
        right.append(self.unsaved_label)
        self.discard_btn = tool_button("edit-undo-symbolic", "Descartar", "Volver a lo que estaba guardado",
                                       self.discard_changes, "flat")
        self.discard_btn.set_visible(False)
        right.append(self.discard_btn)
        self.save_btn = tool_button("document-save-symbolic", "Guardar", "Guardar los cambios de esta voz (Ctrl+S)",
                                    lambda *_: self.save_changes(), "save")
        self.save_btn.set_sensitive(False)
        right.append(self.save_btn)
        self.create_btn = tool_button("audio-input-microphone-symbolic", "Crear voz…",
                                      "Inventa una voz nueva a partir de una descripción", self.on_create_voice, "flat")
        right.append(self.create_btn)
        outer.append(head)

        # en ventanas estrechas la lista lateral se oculta y la voz se elige aquí
        self.voice_pick = Gtk.DropDown(visible=False, margin_top=8, margin_start=12, margin_end=12, enable_search=True)
        self.voice_pick.connect("notify::selected", self.on_voice_pick)
        outer.append(self.voice_pick)

        body = Gtk.Box(vexpand=True)
        self.voice_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.voice_list.add_css_class("navigation-sidebar")
        self.voice_list.set_header_func(self._voice_header)
        self.voice_list.set_filter_func(self._voice_filter)
        self.voice_list.connect("row-selected", self.on_voice_row_selected)
        self.voice_side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, width_request=270)
        self.voice_side.add_css_class("browser")
        self.voice_search = Gtk.SearchEntry(placeholder_text="Buscar voz o personaje")
        self.voice_search.connect("search-changed", lambda *_: self.voice_list.invalidate_filter())
        self.voice_side.append(self.voice_search)
        self.voice_side.append(Gtk.ScrolledWindow(child=self.voice_list, vexpand=True,
                                                  hscrollbar_policy=Gtk.PolicyType.NEVER))
        body.append(self.voice_side)

        self.detail_stack = Gtk.Stack(hexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.detail_stack.add_named(self.build_voice_detail(), "voz")
        self.detail_stack.add_named(self.build_character_detail(), "personaje")
        body.append(self.detail_stack)
        outer.append(body)
        return outer

    def _voice_filter(self, row):
        q = self.voice_search.get_text().strip().lower()
        return not q or q in (row.get_title() + " " + (row.get_subtitle() or "") + " " + row.spec).lower()

    def build_voice_detail(self):
        page = Adw.PreferencesPage()
        self.voice_group = Adw.PreferencesGroup()
        play_row = Adw.ActionRow(title="Probar esta voz",
                                 subtitle="Prueba estándar con preguntas y exclamaciones; se genera una vez y se guarda")
        self.try_stop = Gtk.Button(icon_name="media-playback-stop-symbolic", tooltip_text="Detener",
                                   valign=Gtk.Align.CENTER, visible=False)
        self.try_stop.add_css_class("circular")
        self.try_stop.connect("clicked", lambda *_: self.stop())
        play_row.add_suffix(self.try_stop)
        self.try_btn = Gtk.Button(icon_name="media-playback-start-symbolic", valign=Gtk.Align.CENTER)
        self.try_btn.add_css_class("circular")
        self.try_btn.add_css_class("suggested-action")
        self.try_btn.connect("clicked", self.on_try_voice)
        play_row.add_suffix(self.try_btn)
        self.voice_group.add(play_row)
        self.use_row = Adw.ActionRow(title="Narrador", subtitle="La voz que cuenta la historia")
        self.use_btn = Gtk.Button(label="Usar como narrador", valign=Gtk.Align.CENTER)
        self.use_btn.connect("clicked", self.on_use_voice)
        self.use_row.add_suffix(self.use_btn)
        self.voice_group.add(self.use_row)
        self.save_char_row = Adw.ActionRow(title="Guardar como personaje",
                                           subtitle="Con estos ajustes y un nombre, para usarlo en el texto: —@nombre")
        save_char = Gtk.Button(label="Guardar…", valign=Gtk.Align.CENTER)
        save_char.connect("clicked", self.on_save_as_character)
        self.save_char_row.add_suffix(save_char)
        self.voice_group.add(self.save_char_row)
        page.add(self.voice_group)

        self.voice_sound = SoundControls("Cómo suena", "Cada voz tiene sus propios ajustes. Pulsa «Guardar» "
                                         "(arriba) para conservarlos; «Probar» ya usa lo que estás tocando.",
                                         self.mark_dirty)
        page.add(self.voice_sound.group)

        self.num_group = Adw.PreferencesGroup(
            title="Personaje por número", description="También puedes elegir la voz con un número: empieza la "
                                                      "intervención con la raya y el número: «—2 Hola».")
        self.num_row = Adw.ComboRow(title="Habla como", model=Gtk.StringList.new(
            ["Ninguno"] + [f"—{n}" for n in range(1, 6)]))
        self.num_row.connect("notify::selected", self.on_number_changed)
        self.num_group.add(self.num_row)
        page.add(self.num_group)

        self.del_voice_group = Adw.PreferencesGroup()
        row = Adw.ActionRow(title="Borrar esta voz", subtitle="Se mueve a la papelera; desde ahí se puede recuperar")
        btn = Gtk.Button(label="Borrar…", valign=Gtk.Align.CENTER)
        btn.add_css_class("destructive-action")
        btn.connect("clicked", self.on_delete_voice)
        row.add_suffix(btn)
        self.del_voice_group.add(row)
        page.add(self.del_voice_group)
        return page

    def build_character_detail(self):
        page = Adw.PreferencesPage()
        self.char_group = Adw.PreferencesGroup()
        self.name_row = Adw.EntryRow(title="Nombre", show_apply_button=True)
        self.name_row.connect("apply", self.on_char_rename)
        self.char_group.add(self.name_row)
        self.base_row = Adw.ComboRow(title="Voz base", subtitle="Su timbre; los ajustes de abajo son solo suyos")
        self.base_row.connect("notify::selected", self.on_char_base_changed)
        self.char_group.add(self.base_row)
        self.marker_row = Adw.ActionRow(title="Cómo escribirlo en el texto")
        self.marker_row.add_css_class("property")
        copy = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text="Copiar", valign=Gtk.Align.CENTER)
        copy.add_css_class("flat")
        copy.connect("clicked", self.on_copy_marker)
        self.marker_row.add_suffix(copy)
        self.char_group.add(self.marker_row)
        play_row = Adw.ActionRow(title="Probar este personaje",
                                 subtitle="Prueba estándar con su voz y ajustes; se genera una vez y se guarda")
        self.char_stop = Gtk.Button(icon_name="media-playback-stop-symbolic", tooltip_text="Detener",
                                    valign=Gtk.Align.CENTER, visible=False)
        self.char_stop.add_css_class("circular")
        self.char_stop.connect("clicked", lambda *_: self.stop())
        play_row.add_suffix(self.char_stop)
        self.char_try_btn = Gtk.Button(icon_name="media-playback-start-symbolic", valign=Gtk.Align.CENTER)
        self.char_try_btn.add_css_class("circular")
        self.char_try_btn.add_css_class("suggested-action")
        self.char_try_btn.connect("clicked", self.on_try_character)
        play_row.add_suffix(self.char_try_btn)
        self.char_group.add(play_row)
        page.add(self.char_group)

        self.char_sound = SoundControls("Cómo suena", "Pulsa «Guardar» (arriba) para conservarlos con el nombre "
                                        "del personaje.", self.mark_dirty, speed=True)
        page.add(self.char_sound.group)

        danger = Adw.PreferencesGroup()
        del_row = Adw.ActionRow(title="Eliminar personaje", subtitle="La voz base no se borra")
        del_btn = Gtk.Button(label="Eliminar", valign=Gtk.Align.CENTER)
        del_btn.add_css_class("destructive-action")
        del_btn.connect("clicked", self.on_delete_character)
        del_row.add_suffix(del_btn)
        danger.add(del_row)
        page.add(danger)
        return page

    @staticmethod
    def group_of(spec):
        return "Personajes" if spec.startswith("personaje:") else engine_of(spec)

    @classmethod
    def _voice_header(cls, row, before):
        spec = row.spec
        if before is None or cls.group_of(before.spec) != cls.group_of(spec):
            title = {"Personajes": "PERSONAJES (—@NOMBRE)", "Qwen": "QWEN · MEJOR CALIDAD",
                     "Kokoro": "KOKORO", "Piper": "PIPER · RÁPIDAS"}[cls.group_of(spec)]
            row.set_header(label(title, "stat-label", xalign=0, margin_start=12, margin_top=12, margin_bottom=4))
        else:
            row.set_header(None)

    def entries(self):
        cast = sorted(load_elenco().items(), key=lambda kv: kv[1].get("nombre", kv[0]).lower())
        return [f"personaje:{k}" for k, _ in cast] + self.voices

    def entry_label(self, spec):
        if spec.startswith("personaje:"):
            return load_elenco().get(spec.split(":", 1)[1], {}).get("nombre", spec)
        return short_label(spec)

    def fill_voice_list(self, select=None):
        """Reconstruye la lista lateral (personajes y voces) y selecciona `select` o lo que había."""
        select = select or self.sel_voice or self.current_voice()
        self.entry_specs = self.entries()
        self.syncing = True
        while (row := self.voice_list.get_row_at_index(0)) is not None:
            self.voice_list.remove(row)
        for spec in self.entry_specs:
            row = Adw.ActionRow(title=self.entry_label(spec), activatable=True)
            row.spec = spec
            self.voice_list.append(row)
        self.voice_pick.set_model(Gtk.StringList.new([self.entry_label(s) for s in self.entry_specs]))
        self.syncing = False
        self.update_voice_subtitles()
        if select not in self.entry_specs:
            select = self.entry_specs[0] if self.entry_specs else None
        if select:
            self.sel_voice = None
            self.voice_list.select_row(self.voice_list.get_row_at_index(self.entry_specs.index(select)))

    def update_voice_subtitles(self):
        mapa = md2audio.personajes()
        dialog = md2audio.libro_settings().get("voz_dialogo")
        narrator = self.current_voice()
        cast = load_elenco()
        i = 0
        while (row := self.voice_list.get_row_at_index(i)) is not None:
            if row.spec.startswith("personaje:"):
                slug = row.spec.split(":", 1)[1]
                f = cast.get(slug, {})
                base = short_label("qwen:" + f.get("voz", ""))
                row.set_subtitle(f"—@{slug}" if base == f.get("nombre") else f"—@{slug} · voz {base}")
                i += 1
                continue
            name, tags = qwen_name(row.spec), []
            if row.spec == narrator:
                tags.append("Narrador")
            if name:
                tags += [f"—{n}" for n, v in sorted(mapa.items()) if v == name]
                if dialog == name:
                    tags.append("Diálogos")
            row.set_subtitle(" · ".join(tags))
            i += 1

    def on_voice_row_selected(self, _lb, row):
        if row is None or self.syncing:
            return
        if self.dirty_spec and self.dirty_spec != row.spec:
            prev = self.dirty_spec
            self.ask_unsaved(lambda: self.on_voice_row_selected(None, row), cancel=lambda: self.select_spec(prev))
            return
        self.syncing = True
        self.voice_pick.set_selected(self.entry_specs.index(row.spec))
        self.syncing = False
        self.show_voice(row.spec)

    def on_voice_pick(self, *_):
        if self.syncing:
            return
        row = self.voice_list.get_row_at_index(self.voice_pick.get_selected())
        if row is not None and row is not self.voice_list.get_selected_row():
            self.voice_list.select_row(row)

    def show_voice(self, spec):
        was, self.loading = self.loading, True
        self.sel_voice = spec
        if spec.startswith("personaje:"):
            self.show_character(spec.split(":", 1)[1])
            self.loading = was
            return
        self.detail_stack.set_visible_child_name("voz")
        name = qwen_name(spec)
        meta = md2audio._json(md2audio.QWEN_VOICES / name / "meta.json") if name else {}
        self.voice_group.set_title(short_label(spec))
        self.voice_group.set_description(meta.get("descripcion") or f"Motor {engine_of(spec)}")
        self.voice_sound.group.set_visible(name is not None)
        self.num_group.set_visible(name is not None)
        self.del_voice_group.set_visible(name is not None)
        self.save_char_row.set_visible(name is not None)
        self.refresh_use_button()
        self.update_try_buttons()
        if name:
            self.voice_sound.load(md2audio.qwen_settings(name))
            nums = [n for n, v in md2audio.personajes().items() if v == name]
            self.num_row.set_selected(nums[0] if nums else 0)
        self.loading = was

    def refresh_use_button(self):
        is_narrator = self.sel_voice == self.current_voice()
        self.use_btn.set_label("Es el narrador" if is_narrator else "Usar como narrador")
        self.use_btn.set_sensitive(not is_narrator)

    def on_use_voice(self, _btn):
        if self.sel_voice in self.voices:
            self.voice_dd.set_selected(self.voices.index(self.sel_voice))

    def on_narrator_changed(self, *_):
        self.update_statusbar_voice()
        if self.loading:
            return
        self.update_voice_subtitles()
        self.update_stats()
        if self.sel_voice and not self.sel_voice.startswith("personaje:"):
            self.refresh_use_button()

    # --- cambios sin guardar de la voz o el personaje abierto
    def mark_dirty(self, *_):
        if self.loading or not self.sel_voice:
            return
        self.dirty_spec = self.sel_voice
        self.update_save_ui()

    def update_save_ui(self):
        dirty = self.dirty_spec is not None
        self.save_btn.set_sensitive(dirty)
        (self.save_btn.add_css_class if dirty else self.save_btn.remove_css_class)("suggested-action")
        self.discard_btn.set_visible(dirty)
        self.unsaved_label.set_visible(dirty)

    def save_changes(self):
        """Guarda los ajustes de la voz o del personaje abierto."""
        spec = self.dirty_spec
        if spec is None:
            return
        if spec.startswith("personaje:"):
            slug, cast, names = spec.split(":", 1)[1], load_elenco(), self.base_names()
            if slug in cast:
                cast[slug].update(self.char_sound.values())
                if 0 <= self.base_row.get_selected() < len(names):
                    cast[slug]["voz"] = names[self.base_row.get_selected()]
                save_elenco(cast)
            nombre = cast.get(slug, {}).get("nombre", slug)
        else:
            save_voice_settings(qwen_name(spec), self.voice_sound.values())
            nombre = short_label(spec)
        self.dirty_spec = None
        self.update_save_ui()
        self.update_voice_subtitles()
        self.update_stats()
        self.toast(f"Cambios de «{nombre}» guardados")

    def discard_changes(self, *_):
        spec, self.dirty_spec = self.dirty_spec, None
        self.update_save_ui()
        if spec and spec == self.sel_voice:
            self.show_voice(spec)

    def ask_unsaved(self, then, cancel=None):
        """¿Guardar los cambios pendientes antes de seguir? Guardar / Descartar / Cancelar."""
        spec = self.dirty_spec
        nombre = (load_elenco().get(spec.split(":", 1)[1], {}).get("nombre") if spec.startswith("personaje:")
                  else short_label(spec))
        dlg = Adw.AlertDialog(heading=f"¿Guardar los cambios de «{nombre}»?",
                              body="Si no los guardas, la voz se queda como estaba.")
        dlg.add_response("cancel", "Cancelar")
        dlg.add_response("discard", "Descartar")
        dlg.add_response("save", "Guardar")
        dlg.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("save")
        dlg.set_close_response("cancel")

        def done(_d, response):
            if response == "save":
                self.save_changes()
            elif response == "discard":
                self.dirty_spec = None
                self.update_save_ui()
            else:
                if cancel:
                    cancel()
                return
            then()
        dlg.connect("response", done)
        dlg.present(self)

    def select_spec(self, spec):
        """Vuelve a marcar `spec` en la lista sin recargar sus ajustes (al cancelar un cambio de voz)."""
        if spec in self.entry_specs:
            self.syncing = True
            self.voice_list.select_row(self.voice_list.get_row_at_index(self.entry_specs.index(spec)))
            self.voice_pick.set_selected(self.entry_specs.index(spec))
            self.syncing = False

    # --- borrar una voz de Qwen
    def on_delete_voice(self, _btn):
        name = qwen_name(self.sel_voice)
        if not name:
            return
        usan = [f["nombre"] for f in load_elenco().values() if f.get("voz") == name]
        body = "La carpeta de la voz se mueve a la papelera; desde ahí puedes recuperarla."
        if usan:
            body += f"\n\nEstos personajes usan esta voz y también se borrarán: {', '.join(usan)}."
        if self.sel_voice == self.current_voice():
            body += "\n\nEs el narrador actual: se elegirá otra voz."
        dlg = Adw.AlertDialog(heading=f"¿Borrar la voz «{short_label(self.sel_voice)}»?", body=body)
        dlg.add_response("cancel", "Cancelar")
        dlg.add_response("ok", "Borrar")
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_close_response("cancel")
        dlg.connect("response", lambda _d, r: r == "ok" and self.delete_voice(name))
        dlg.present(self)

    def delete_voice(self, name):
        """Manda la voz a la papelera y quita todo lo que la usaba (números, diálogos, personajes, pruebas)."""
        folder = md2audio.QWEN_VOICES / name
        try:
            Gio.File.new_for_path(str(folder)).trash(None)
        except GLib.Error as e:
            self.toast(f"No se pudo borrar: {e.message}")
            return
        mapa = {n: v for n, v in md2audio.personajes().items() if v != name}
        write_json(md2audio.PERSONAJES, {str(n): v for n, v in sorted(mapa.items())})
        libro = md2audio._json(md2audio.LIBRO_FILE)
        if libro.get("voz_dialogo") == name:
            libro.pop("voz_dialogo")
            write_json(md2audio.LIBRO_FILE, libro)
        cast = load_elenco()
        for slug in [k for k, f in cast.items() if f.get("voz") == name]:
            cast.pop(slug)
            for f in pruebas.DIR.glob(f"personaje_{slug}.*"):
                f.unlink(missing_ok=True)
        save_elenco(cast)
        for f in pruebas.DIR.glob(f"qwen_{name}.*"):
            f.unlink(missing_ok=True)
        self.dirty_spec = None
        self.update_save_ui()
        self.sel_voice = self.sel_char = None
        self.reload_voices()
        self.fill_voice_list()
        self.update_stats()
        self.toast(f"Voz borrada (está en la papelera)")

    def on_number_changed(self, *_):
        name = qwen_name(self.sel_voice)
        if self.loading or name is None:
            return
        mapa = {n: v for n, v in md2audio.personajes().items() if v != name}
        if self.num_row.get_selected() > 0:
            mapa[self.num_row.get_selected()] = name
        write_json(md2audio.PERSONAJES, {str(n): v for n, v in sorted(mapa.items())})
        self.update_voice_subtitles()
        self.update_stats()

    def on_try_voice(self, _btn):
        if self.sel_voice and not self.sel_voice.startswith("personaje:"):
            self.try_sample(self.sel_voice, short_label(self.sel_voice))

    # --- personajes con nombre
    def base_names(self):
        return md2audio.qwen_profiles()

    def show_character(self, slug):
        f = load_elenco().get(slug)
        if f is None:
            return
        self.sel_char = slug
        self.detail_stack.set_visible_child_name("personaje")
        names = self.base_names()
        self.char_group.set_title(f["nombre"])
        self.char_group.set_description("Una voz con nombre: sus ajustes se guardan y se usan al escribir "
                                        f"«—@{slug}» al empezar su intervención.")
        self.name_row.set_text(f["nombre"])
        self.base_row.set_model(Gtk.StringList.new([short_label("qwen:" + n) for n in names]))
        self.base_row.set_selected(names.index(f["voz"]) if f["voz"] in names else 0)
        self.marker_row.set_subtitle(f"—@{slug} Hola, ¿qué tal?")
        self.char_sound.load({**md2audio.ficha_ajustes(f), "velocidad": f.get("velocidad", 1.0)})
        self.update_try_buttons()

    def on_char_base_changed(self, *_):
        self.mark_dirty()

    def on_char_rename(self, row):
        old, cast = self.sel_char, load_elenco()
        nombre = row.get_text().strip()
        new = md2audio.texto_es.slug(nombre)
        if old not in cast or not new:
            return
        if new != old and new in cast:
            self.toast("Ya hay un personaje con ese nombre")
            return
        ficha = cast.pop(old)
        ficha["nombre"] = nombre
        cast[new] = ficha
        save_elenco(cast)
        self.fill_voice_list(select=f"personaje:{new}")
        self.update_stats()
        if new != old:
            self.toast(f"Ahora se escribe —@{new}. Cambia el texto donde usabas «—@{old}»")

    def on_copy_marker(self, _btn):
        if self.sel_char:
            Gdk.Display.get_default().get_clipboard().set(f"—@{self.sel_char} ")
            self.toast("Copiado")

    def on_try_character(self, _btn):
        slug, cast = self.sel_char, load_elenco()
        if slug in cast:
            self.try_sample(f"personaje:{slug}", cast[slug]["nombre"])

    # --- pruebas de voz guardadas: se generan una vez (al crear la voz) y luego solo se reproducen
    def try_sample(self, spec, nombre):
        if self.proc and self.preview_spec == spec:  # ya está sonando: el mismo botón pausa y sigue
            self.on_pause_read(None)
            return
        if self.dirty_spec == spec:
            self.stop()
            if spec.startswith("personaje:"):
                names = self.base_names()
                voz = "qwen:" + names[self.base_row.get_selected()]
                vals = self.char_sound.values()
                speed = vals.pop("velocidad", 1.0)
            else:
                voz, vals, speed = spec, self.voice_sound.values(), 1.0
            self.play(pruebas.texto(), voice=voz, status=f"Probando cambios de {nombre}…",
                      extra=["--qwen-ajustes", json.dumps(vals)], speed_mul=speed / self.speed_adj.get_value(),
                      preview=spec)
            return
        r = pruebas.receta(spec)
        if r is None:
            return
        self.stop()
        archivo, clave, _args = r
        voz = spec if not spec.startswith("personaje:") else "qwen:" + load_elenco()[spec.split(":", 1)[1]]["voz"]
        if pruebas.vigente(archivo, clave):
            self.play("", voice=voz, status=f"Prueba de {nombre}", source=pruebas.ruta(archivo), preview=spec)
        else:
            self.make_sample(spec, nombre, play_after=voz)

    def update_try_buttons(self):
        """Los botones de «Probar» muestran pausa mientras suena su prueba, y detener al lado."""
        for btn, stop, spec in ((self.try_btn, self.try_stop, self.sel_voice),
                                (self.char_try_btn, self.char_stop, f"personaje:{self.sel_char}")):
            active = self.proc is not None and spec is not None and self.preview_spec == spec
            playing = active and not self.read_paused
            btn.set_icon_name("media-playback-pause-symbolic" if playing else "media-playback-start-symbolic")
            btn.set_tooltip_text("Pausa" if playing else "Seguir" if active else
                                 "Generando la prueba…" if spec in self.generating else "Escuchar la prueba")
            btn.set_sensitive(active or spec not in self.generating)
            stop.set_visible(active)

    def make_sample(self, spec, nombre, play_after=None):
        """Genera en segundo plano la prueba de una voz o personaje y la guarda (y la reproduce, si play_after)."""
        r = pruebas.receta(spec)
        if r is None or spec in self.generating:
            return
        archivo, clave, args = r
        self.generating.add(spec)
        proc = subprocess.Popen(pruebas.comando(archivo, args), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True, preexec_fn=die_with_app)
        if play_after:
            self.read_status.set_label("Generando la prueba…")
        self.set_status(f"Generando la prueba de voz de {nombre} (solo esta vez)…", "busy")
        self.update_try_buttons()

        def watch():
            ok = proc.wait() == 0 and pruebas.terminar(archivo, clave)
            GLib.idle_add(done, ok)

        def done(ok):
            self.generating.discard(spec)
            if self.proc is None:
                self.set_status("Listo")
            if not ok:
                self.toast(f"No se pudo generar la prueba de {nombre}")
            elif play_after and self.proc is None:
                self.play("", voice=play_after, status=f"Prueba de {nombre}", source=pruebas.ruta(archivo), preview=spec)
            self.update_try_buttons()
            return False
        threading.Thread(target=watch, daemon=True).start()

    def on_delete_character(self, _btn):
        slug, cast = self.sel_char, load_elenco()
        if slug not in cast:
            return
        dlg = Adw.AlertDialog(heading=f"¿Eliminar a {cast[slug]['nombre']}?",
                              body="Se borran su nombre y sus ajustes. La voz base se queda como está.")
        dlg.add_response("cancel", "Cancelar")
        dlg.add_response("ok", "Eliminar")
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_close_response("cancel")

        def done(_d, response):
            if response == "ok":
                self.delete_character(slug)
        dlg.connect("response", done)
        dlg.present(self)

    def delete_character(self, slug):
        if self.dirty_spec == f"personaje:{slug}":
            self.dirty_spec = None
            self.update_save_ui()
        cast = load_elenco()
        cast.pop(slug, None)
        save_elenco(cast)
        self.sel_voice = self.sel_char = None
        self.fill_voice_list()
        self.update_stats()

    def make_character(self, nombre, voz, sampling=None):
        nombre, cast = nombre.strip(), load_elenco()
        slug = md2audio.texto_es.slug(nombre)
        if not slug:
            self.toast("Escribe un nombre")
            return
        if slug in cast:
            self.toast("Ya hay un personaje con ese nombre")
            return
        base = md2audio.qwen_settings(voz)
        cast[slug] = {"nombre": nombre, "voz": voz, "velocidad": 1.0,
                      **(sampling or {k: base[k] for k in md2audio.VOICE_KEYS})}
        save_elenco(cast)
        self.stack.set_visible_child_name("voces")
        self.fill_voice_list(select=f"personaje:{slug}")
        self.update_stats()
        self.toast(f"Personaje «{nombre}»: escríbelo como —@{slug}")
        if not cola.has_work():  # con la cola trabajando, la GPU está ocupada: se hará al pulsar «Probar»
            self.make_sample(f"personaje:{slug}", nombre)

    def name_dialog(self, heading, body, ok_label, callback, with_voice=False, with_desc=False):
        dlg = Adw.AlertDialog(heading=heading, body=body)
        dlg.add_response("cancel", "Cancelar")
        dlg.add_response("ok", ok_label)
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("ok")
        dlg.set_close_response("cancel")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        name = Gtk.Entry(placeholder_text="Nombre (p. ej. Marta)", activates_default=True)
        box.append(name)
        desc = voice = None
        if with_desc:
            desc = Gtk.Entry(placeholder_text="Cómo suena: «Mujer de 40 años, voz grave y pausada, acento mexicano»",
                             activates_default=True)
            box.append(desc)
        if with_voice:
            names = self.base_names()
            voice = Gtk.DropDown(model=Gtk.StringList.new([short_label("qwen:" + n) for n in names]),
                                 enable_search=True)
            cur = qwen_name(self.sel_voice) or qwen_name(self.current_voice())
            if cur in names:
                voice.set_selected(names.index(cur))
            box.append(voice)
        dlg.set_extra_child(box)

        def done(_d, response):
            if response == "ok":
                callback(name.get_text(), desc.get_text() if desc else None,
                         self.base_names()[voice.get_selected()] if voice else None)
        dlg.connect("response", done)
        dlg.present(self)

    def on_new_character(self, _btn):
        self.name_dialog("Nuevo personaje",
                         "El nombre es lo que escribirás tras la raya: —@marta. Elige la voz en la que se basa; "
                         "luego podrás ajustar su temperatura y velocidad.", "Crear",
                         lambda n, _d, v: self.make_character(n, v), with_voice=True)

    def on_save_as_character(self, _btn):
        name = qwen_name(self.sel_voice)
        if name:
            values = dict(self.voice_sound.values())
            self.name_dialog("Guardar como personaje",
                             "Se guarda esta voz con sus ajustes actuales bajo un nombre.", "Guardar",
                             lambda n, _d, _v: self.make_character(n, name, values))

    # --- voces nuevas (Qwen VoiceDesign)
    def on_create_voice(self, _btn):
        self.name_dialog("Crear una voz nueva",
                         "Describe cómo suena (edad, timbre, ritmo, acento). Tarda un minuto y no se necesita "
                         "internet. Se podrá usar como cualquier otra voz.", "Crear",
                         lambda n, d, _v: self.run_create_voice(n, d), with_desc=True)

    def run_create_voice(self, nombre, descripcion):
        nombre, descripcion = nombre.strip(), (descripcion or "").strip()
        vid = md2audio.texto_es.slug(nombre)
        if not vid or len(descripcion) < 10:
            self.toast("Escribe un nombre y una descripción de la voz")
            return
        if vid in self.base_names():
            self.toast("Ya hay una voz con ese nombre")
            return
        if cola.has_work():
            self.toast("Hay conversiones en la cola: espera a que terminen (la GPU está ocupada)")
            return
        if not QWEN_PY.exists() or not CREAR_VOZ.exists():
            self.toast("Falta el entorno de Qwen")
            return
        self.stop()
        job = rutas.CACHE / "nueva_voz.json"
        job.parent.mkdir(parents=True, exist_ok=True)
        job.write_text(json.dumps([{"id": vid, "label": nombre, "descripcion": descripcion, "semilla": 1234}]))
        proc = subprocess.Popen([str(QWEN_PY), str(CREAR_VOZ), str(job)], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, start_new_session=True, preexec_fn=die_with_app)
        self.create_btn.set_sensitive(False)
        self.create_spinner.start()
        self.create_status.set_label(f"Creando «{nombre}»…")
        self.set_status(f"Creando la voz «{nombre}»…", "busy")

        def watch():
            ok, err = False, None
            for line in proc.stdout:
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("type") == "voz":
                    ok = True
                elif ev.get("type") == "error":
                    err = ev.get("message")
            proc.wait()
            GLib.idle_add(self.finish_create_voice, vid, nombre, ok, err)
        threading.Thread(target=watch, daemon=True).start()

    def finish_create_voice(self, vid, nombre, ok, err):
        self.create_spinner.stop()
        self.create_status.set_label("")
        self.create_btn.set_sensitive(True)
        self.set_status("Listo")
        if not ok:
            self.toast(f"No se pudo crear la voz: {err or 'error desconocido'}")
            return
        self.reload_voices()
        self.fill_voice_list(select=f"qwen:{vid}")
        self.toast(f"Voz «{nombre}» creada; preparando su prueba de voz")
        self.make_sample(f"qwen:{vid}", nombre)

    def reload_voices(self):
        """Vuelve a leer las voces instaladas (tras crear una) sin perder el narrador elegido."""
        orden = ("Qwen", "Kokoro", "Piper")
        cur = self.current_voice()
        self.rates = list_voices()
        self.voices = sorted(self.rates, key=lambda v: orden.index(engine_of(v)))
        was, self.loading = self.loading, True
        self.voice_model.splice(0, self.voice_model.get_n_items(), [voice_label(v) for v in self.voices])
        self.voice_dd.set_selected(self.voices.index(cur) if cur in self.voices else 0)
        self.load_libro_ui()
        self.loading = was

    # ------------------------------------------------------------ página: Audiolibro (ajustes comunes)
    def build_settings_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        head, right = strip("Ajustes del audiolibro")
        right.append(tool_button("document-edit-symbolic", "Diccionario de pronunciación",
                                 "Una línea por palabra: «Edward = Édguard»", lambda *_: self.launch(DICCIONARIO),
                                 "flat"))
        right.append(tool_button("edit-undo-symbolic", "Restablecer", "Volver a los valores de fábrica de esta página",
                                 self.on_libro_reset, "flat"))
        outer.append(head)
        page = Adw.PreferencesPage(vexpand=True)
        outer.append(page)
        self.libro_widgets = {}

        fast = Adw.PreferencesGroup()
        row = Adw.SwitchRow(title="⚡ Modo flash",
                            subtitle="Más rápido: no se revisa con Whisper y todo lo lee el narrador "
                                     "(se ignoran las voces de los diálogos y personajes)")
        fast.add(row)
        self.libro_widgets["flash"] = row
        page.add(fast)

        pauses = Adw.PreferencesGroup(title="Pausas",
                                      description="Silencio que se deja al leer un libro con las voces de Qwen.")
        for key, title, sub, hi in (
                ("pausa_frase", "Entre frases largas", "Cuando un párrafo se parte en varios fragmentos", 1.5),
                ("pausa_parrafo", "Entre párrafos", "", 2.0),
                ("pausa_titulo_antes", "Antes de un título", "", 3.0),
                ("pausa_titulo_despues", "Después de un título", "", 3.0),
                ("pausa_escena", "En un cambio de escena", "Una línea con --- o ***", 5.0),
                ("pausa_voz", "Al cambiar de voz", "Dentro de un párrafo, entre narrador y personaje", 1.0)):
            row, scale = scale_row(title, sub, 0.0, hi, 0.05, lambda v: f"{v:.2f} s")
            pauses.add(row)
            self.libro_widgets[key] = scale
        page.add(pauses)

        dialogs = Adw.PreferencesGroup(title="Diálogos",
                                       description="Una raya (—) sin marca usa la voz de los diálogos. "
                                                   "«—2 Hola» elige la voz por número y «—@marta Hola», "
                                                   "un personaje con nombre. Se asignan en Voces.")
        self.dialog_row = Adw.ComboRow(title="Voz de los diálogos", enable_search=True)
        dialogs.add(self.dialog_row)
        page.add(dialogs)
        self.dialogs_group = dialogs

        quality = Adw.PreferencesGroup(title="Calidad del audio")
        for key, title, sub in (
                ("revisar", "Revisar con Whisper", "Escucha cada fragmento y regenera los que salgan mal"),
                ("nivelar", "Igualar el volumen", "Todos los fragmentos al mismo nivel (≈ −19 LUFS)"),
                ("normalizar_texto", "Leer cifras como palabras",
                 "Números, fechas, horas, romanos, abreviaturas y rayas de diálogo"),
                ("recortar_silencios", "Recortar silencios sobrantes", "Las pausas las decides tú arriba")):
            row = Adw.SwitchRow(title=title, subtitle=sub)
            quality.add(row)
            self.libro_widgets[key] = row
        page.add(quality)
        return outer

    def load_libro_ui(self):
        """Muestra los ajustes guardados y solo después conecta las señales (así no se guarda nada al cargar)."""
        was, self.loading = self.loading, True
        cfg = md2audio.libro_settings()
        for key, w in self.libro_widgets.items():
            if isinstance(w, Gtk.Scale):
                w.set_value(cfg[key])
            else:
                w.set_active(bool(cfg[key]))
        names = md2audio.qwen_profiles()
        self.dialog_row.set_model(Gtk.StringList.new(["La misma voz"] + [short_label("qwen:" + n) for n in names]))
        self.dialog_row.set_selected(1 + names.index(cfg["voz_dialogo"]) if cfg.get("voz_dialogo") in names else 0)
        if not getattr(self, "_libro_connected", False):
            self._libro_connected = True
            for w in self.libro_widgets.values():
                w.connect("value-changed" if isinstance(w, Gtk.Scale) else "notify::active", self.on_libro_changed)
            self.dialog_row.connect("notify::selected", self.on_libro_changed)
        self.update_flash_ui()
        self.loading = was

    def update_flash_ui(self):
        """En modo flash, lo que no se usa (Whisper y las voces de los diálogos) se ve apagado."""
        flash = self.libro_widgets["flash"].get_active()
        if getattr(self, "flash_badge", None):
            self.flash_badge.set_visible(flash)
        self.libro_widgets["revisar"].set_sensitive(not flash)
        self.dialogs_group.set_sensitive(not flash)

    def on_libro_changed(self, *_):
        if self.loading:
            return
        cfg = {k: (round(w.get_value(), 2) if isinstance(w, Gtk.Scale) else w.get_active())
               for k, w in self.libro_widgets.items()}
        names, i = md2audio.qwen_profiles(), self.dialog_row.get_selected()
        cfg["voz_dialogo"] = names[i - 1] if 0 < i <= len(names) else None
        save_libro(cfg)
        self.update_flash_ui()
        self.update_voice_subtitles()
        self.update_stats()

    def on_libro_reset(self, _btn):
        md2audio.LIBRO_FILE.unlink(missing_ok=True)
        self.load_libro_ui()
        self.update_voice_subtitles()
        self.update_stats()
        self.toast("Ajustes restablecidos")

    # ------------------------------------------------------------ menú
    def on_shortcuts(self, *_):
        dlg = Adw.AlertDialog(heading="Atajos de teclado")
        grid = Gtk.Grid(column_spacing=24, row_spacing=8)
        for i, (keys, what) in enumerate((
                ("Ctrl+Intro", "Leer / pausar"), ("Esc", "Detener"), ("Ctrl+O", "Abrir y leer un archivo"),
                ("Ctrl+Mayús+E", "Exportar el texto a audio"), ("Ctrl+1 … 4", "Cambiar de página"))):
            grid.attach(label(keys, "chip", xalign=0, halign=Gtk.Align.START), 0, i, 1, 1)
            grid.attach(label(what, xalign=0), 1, i, 1, 1)
        dlg.set_extra_child(grid)
        dlg.add_response("ok", "Cerrar")
        dlg.present(self)

    def on_about(self, *_):
        Adw.AboutDialog(application_name="Juglar", application_icon=ICON, version=VERSION,
                        comments="Lectura en voz alta y audiolibros con una voz para cada personaje, "
                                 "en local: Qwen3-TTS, Kokoro y Piper.",
                        developer_name="YeisenK", website=WEBSITE, issue_url=WEBSITE + "/issues",
                        license_type=Gtk.License.MIT_X11).present(self)

    # ------------------------------------------------------------ utilidades
    def toast(self, msg):
        self.toasts.add_toast(Adw.Toast(title=msg, timeout=3))

    def get_text(self):
        s, e = self.buffer.get_bounds()
        return self.buffer.get_text(s, e, False).strip()

    def current_voice(self):
        i = self.voice_dd.get_selected()
        return self.voices[i] if 0 <= i < len(self.voices) else None

    def engine_args(self, voice=None, speed_mul=1.0):
        return ["-v", voice or self.current_voice(), "-s", f"{self.speed_adj.get_value() * speed_mul:.3f}"]

    def launch(self, path, folder=False):
        if not path:
            return
        launcher = Gtk.FileLauncher.new(Gio.File.new_for_path(str(path)))
        if folder:
            launcher.open_containing_folder(self, None, None)
        else:
            launcher.launch(self, None, None)

    def file_dialog(self, title):
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter(name="Markdown y texto")
        for ext in TEXT_EXTS:
            f.add_suffix(ext.lstrip("."))
        filters.append(f)
        dialog = Gtk.FileDialog(title=title, filters=filters)
        if self.cfg.get("last_dir") and Path(self.cfg["last_dir"]).is_dir():
            dialog.set_initial_folder(Gio.File.new_for_path(self.cfg["last_dir"]))
        return dialog

    # ------------------------------------------------------------ lectura en voz alta
    def set_playing(self, playing):
        self.read_paused = False
        self.stop_btn.set_sensitive(playing)
        self.play_btn.set_icon_name("media-playback-pause-symbolic" if playing else "media-playback-start-symbolic")
        self.play_btn.set_tooltip_text("Pausa (Ctrl+Intro)" if playing else "Leer (Ctrl+Intro)")
        if not playing:
            self.preview_spec = None
            self.update_try_buttons()
            self.read_status.set_label("Listo")
            self.timecode.set_label("00:00:00")
            self.set_status("Listo")

    def on_play_clicked(self, _btn):
        if self.proc:
            self.on_pause_read(None)
        else:
            self.play(self.get_text())

    def play(self, text, voice=None, status="Leyendo…", extra=None, speed_mul=1.0, source=None, preview=None):
        voice = voice or self.current_voice()
        self.preview_spec = preview
        if not text and not source:
            self.toast("No hay texto para leer")
            return
        if not voice:
            self.toast("No hay ninguna voz instalada")
            return
        rate = self.rates[voice]
        # md2audio -> (esta app) -> aplay, cada uno en su grupo y ligado a la vida de la app
        if source:  # una prueba ya guardada: solo hay que decodificarla
            cmd = ["ffmpeg", "-loglevel", "error", "-i", str(source), "-f", "s16le", "-ac", "1", "-ar", str(rate), "-"]
        else:
            cmd = [str(VENV_PY), "-I", str(MD2AUDIO), "-", "--raw", *self.engine_args(voice, speed_mul), *(extra or [])]
        tts = subprocess.Popen(cmd, stdin=subprocess.DEVNULL if source else subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, process_group=0, preexec_fn=die_with_app)
        player = subprocess.Popen(["aplay", "-q", "-r", str(rate), "-f", "S16_LE", "-t", "raw", "-c", "1", "-"],
                                  stdin=subprocess.PIPE, process_group=tts.pid, preexec_fn=die_with_app)
        self.proc = tts

        def feed():  # en un hilo: un archivo grande no debe congelar la ventana mientras arranca el motor
            try:
                tts.stdin.write(text.encode())
                tts.stdin.close()
            except (BrokenPipeError, ValueError, OSError):
                pass

        def show(secs):
            if self.proc is tts:
                self.timecode.set_label(timecode(secs))
                if not self.read_paused:
                    self.read_status.set_label(status)
                    self.set_status(f"{status} {fmt_time(secs)}", "busy")
            return False

        def pump():  # pasa el audio al reproductor y va contando el tiempo leído
            sent, last = 0, -1
            try:
                while chunk := tts.stdout.read1(65536):
                    player.stdin.write(chunk)
                    sent += len(chunk)
                    secs = sent // (rate * 2)
                    if secs != last:
                        last = secs
                        GLib.idle_add(show, secs)
            except (BrokenPipeError, ValueError, OSError):
                pass
            finally:
                with contextlib.suppress(Exception):
                    player.stdin.close()

        if not source:
            threading.Thread(target=feed, daemon=True).start()
        threading.Thread(target=pump, daemon=True).start()
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, tts.pid, lambda *_: None)  # recoger el proceso
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, player.pid, lambda *_: self.on_finished(tts))
        self.set_playing(True)
        self.update_try_buttons()
        self.read_status.set_label("Preparando la voz…")
        self.set_status("Preparando la voz…", "busy")

    def on_finished(self, proc):
        if self.proc is proc:
            self.proc = None
            self.set_playing(False)

    def stop(self):
        if self.proc:
            for sig in (signal.SIGTERM, signal.SIGCONT):  # un grupo en pausa no recibe SIGTERM hasta reanudarse
                try:
                    os.killpg(self.proc.pid, sig)
                except ProcessLookupError:
                    pass
            self.proc = None
        self.set_playing(False)

    def on_pause_read(self, _btn):
        if not self.proc:
            return
        self.read_paused = not self.read_paused
        try:
            os.killpg(self.proc.pid, signal.SIGSTOP if self.read_paused else signal.SIGCONT)
        except ProcessLookupError:
            return
        self.play_btn.set_icon_name("media-playback-start-symbolic" if self.read_paused
                                    else "media-playback-pause-symbolic")
        self.play_btn.set_tooltip_text("Seguir (Ctrl+Intro)" if self.read_paused else "Pausa (Ctrl+Intro)")
        self.read_status.set_label("En pausa" if self.read_paused else "Leyendo…")
        self.set_status("En pausa" if self.read_paused else "Leyendo…", "paused" if self.read_paused else "busy")
        self.update_try_buttons()

    def read_file(self, path):
        """Carga un archivo en el editor y lo lee en voz alta ahora mismo."""
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace").strip()
        except OSError as e:
            self.toast(f"No se pudo abrir el archivo: {e.strerror}")
            return
        self.stop()
        self.doc_name = Path(path).name
        self.doc_label.set_label(str(path))
        self.stack.set_visible_child_name("leer")
        self.on_page_changed()
        self.buffer.set_text(text)
        self.play(text)

    def on_read_file(self, _btn):
        self.file_dialog("Elige el archivo a leer").open(self, None, self._read_file_done)

    def _read_file_done(self, dialog, res):
        try:
            path = dialog.open_finish(res).get_path()
        except GLib.Error:
            return
        self.cfg["last_dir"] = str(Path(path).parent)
        self.read_file(path)

    def on_paste_read(self, _btn):
        Gdk.Display.get_default().get_clipboard().read_text_async(None, self._pasted)

    def _pasted(self, clip, res):
        try:
            text = clip.read_text_finish(res)
        except GLib.Error:
            text = None
        if not text:
            self.toast("El portapapeles no contiene texto")
            return
        self.buffer.set_text(text)
        self.stop()
        self.play(text.strip())

    # ------------------------------------------------------------ cola de conversión
    def enqueue(self, paths):
        if not self.current_voice():
            self.toast("No hay ninguna voz instalada")
            return
        voice, speed = self.current_voice(), round(self.speed_adj.get_value(), 3)
        ext = FORMATS[self.format_row.get_selected()]
        for path in paths:
            path = Path(path)
            cola.add_job(path, path.with_suffix("." + ext), voice, speed)
            self.cfg["last_dir"] = str(path.parent)
        self.stack.set_visible_child_name("cola")
        self.toast(f"{len(paths)} archivo(s) en la cola")
        self.refresh_queue()

    def on_drop(self, _target, gfile, _x, _y):
        self.dropzone.remove_css_class("hover")
        path = gfile.get_path()
        if path and Path(path).suffix.lower() in TEXT_EXTS:
            self.enqueue([path])
            return True
        self.toast("Arrastra un archivo .md o .txt")
        return False

    def on_convert(self, _btn):
        self.file_dialog("Elige los archivos a convertir").open_multiple(self, None, self._open_done)

    def _open_done(self, dialog, res):
        try:
            files = dialog.open_multiple_finish(res)
        except GLib.Error:
            return
        self.enqueue([files.get_item(i).get_path() for i in range(files.get_n_items())])

    def on_pause_clicked(self, _btn):
        cola.set_paused(not cola.snapshot()["paused"])
        self.refresh_queue()

    def poll_queue(self):
        try:
            mtime = cola.QUEUE.stat().st_mtime_ns
        except OSError:
            mtime = None
        if mtime != self.queue_mtime:
            self.refresh_queue()
        return True

    def refresh_queue(self):
        try:
            self.queue_mtime = cola.QUEUE.stat().st_mtime_ns
        except OSError:
            self.queue_mtime = None
        q = cola.snapshot()
        jobs, paused = q["jobs"], q["paused"]
        ids = {j["id"] for j in jobs}
        for job_id in [i for i in self.rows if i not in ids]:
            row = self.rows.pop(job_id)
            self.job_list.remove(row.row)
        for job in jobs:
            row = self.rows.get(job["id"])
            if row is None:
                row = self.rows[job["id"]] = JobRow(self, job["id"])
                self.job_list.append(row.row)
            row.update(job, paused)
        active = [j for j in jobs if j["status"] in ("queued", "running")]
        running = next((j for j in jobs if j["status"] == "running"), None)
        self.queue_stack.set_visible_child_name("lista" if jobs else "vacio")
        self.clear_btn.set_visible(any(j["status"] in cola.FINISHED for j in jobs))
        self.pause_btn.set_visible(bool(active) or paused)
        self.pause_btn.set_child(Adw.ButtonContent(
            icon_name="media-playback-start-symbolic" if paused else "media-playback-pause-symbolic",
            label="Reanudar" if paused else "Pausar"))
        if running:
            pct = running["done"] * 100 // max(running["total"], 1)
            text = f"Exportando «{running['title']}» · {pct} %" + (" · en pausa" if paused else "")
        elif active:
            text = f"Cola: {len(active)} en espera" + (" · en pausa" if paused else "")
        else:
            done = sum(j["status"] == "done" for j in jobs)
            text = f"Cola: {done} terminado(s)" if done else "Cola vacía"
        self.sb_queue.set_label(text)

    # ------------------------------------------------------------ cierre
    def on_close(self, *_):
        if self.dirty_spec:
            self.stack.set_visible_child_name("voces")
            self.ask_unsaved(self.close)
            return True
        self.stop()  # la cola sigue en segundo plano
        self.cfg.update(voice=self.current_voice(), speed=self.speed_adj.get_value(), text=self.get_text(),
                        audio_ext=FORMATS[self.format_row.get_selected()],
                        page=self.stack.get_visible_child_name())
        save_config(self.cfg)
        return False


class JuglarApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.read_on_open = False
        self.add_main_option("leer", ord("l"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Leer en voz alta el archivo indicado (en la ventana ya abierta, si la hay)", None)
        self.connect("handle-local-options", self.on_local_options)
        action = Gio.SimpleAction.new("leer", GLib.VariantType.new("s"))
        action.connect("activate", lambda _a, param: self.read_path(param.get_string()))
        self.add_action(action)

    def do_startup(self):
        Adw.Application.do_startup(self)
        # tema oscuro de estudio, siempre; y el icono de la app, aunque no esté instalado en el sistema
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(str(rutas.RAIZ / "data"))
        if ESTILO.exists():
            css = Gtk.CssProvider()
            css.load_from_path(str(ESTILO))
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                      Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def on_local_options(self, _app, options):
        if not options.contains("leer"):
            return -1
        paths = [str(Path(a).resolve()) for a in sys.argv[1:] if not a.startswith("-")]
        if not paths:
            print("Uso: juglar --leer archivo.md", file=sys.stderr)
            return 1
        self.register(None)
        if self.get_is_remote():  # ya hay una ventana abierta: mandarle el archivo y salir
            self.activate_action("leer", GLib.Variant("s", paths[0]))
            return 0
        self.read_on_open = True
        return -1

    def read_path(self, path):
        self.do_activate()
        self.get_active_window().read_file(path)

    def do_activate(self):
        win = self.get_active_window() or JuglarWindow(self)
        win.present()

    def do_open(self, files, _n, _hint):
        # "Abrir con Juglar" desde el gestor de archivos: convertir a audio (o leer, con --leer)
        self.do_activate()
        paths = [f.get_path() for f in files if f.get_path()]
        if paths and self.read_on_open:
            self.get_active_window().read_file(paths[0])
        elif paths:
            self.get_active_window().enqueue(paths)


if __name__ == "__main__":
    sys.exit(JuglarApp().run(sys.argv))
