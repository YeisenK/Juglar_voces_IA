#!/usr/bin/env python3
"""Cola de conversión de texto a audio (md2audio) con pausa y ejecución en segundo plano.

Un proceso residente (`cola.py daemon`, lanzado con systemd-run --user) va tomando los trabajos
de la cola de uno en uno. Es independiente de la ventana: sigue con la pantalla apagada o bloqueada,
y mientras convierte impide que el equipo se suspenda solo. El estado vive en un JSON con candado.

Uso: juglar-cola add ARCHIVO... | libro CARPETA | rehacer AUDIO N [--texto T] | rehacer AUDIO --md CORREGIDO.md
                  | musica CANCIÓN.md... | musica -d DESCRIPCIÓN [--letra ARCHIVO] [-t SEGUNDOS] [-o SALIDA]
                  | list | pause | resume | cancel ID | remove ID | clear
"""
import argparse
import ctypes
import fcntl
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))
import rutas  # noqa: E402

VENV_PY = rutas.VENV_PY
MD2AUDIO = APP_DIR / "md2audio.py"
MUSICA_WORKER = rutas.MOTORES / "musica_worker.py"
STATE = rutas.STATE / "cola"
QUEUE = STATE / "cola.json"
LOCK = STATE / "cola.lock"
DAEMON_LOCK = STATE / "daemon.lock"
TEXTS = STATE / "textos"
LOG = STATE / "cola.log"
HISTORIAL = STATE / "historial.json"   # audios exportados (se muestran mientras sigan existiendo)
DEFAULT_VOICE = "qwen:narradora"
FINISHED = ("done", "failed", "cancelled")

_libc = ctypes.CDLL(None, use_errno=True)


# ---------------------------------------------------------------- estado

@contextmanager
def locked():
    STATE.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def load():
    try:
        q = json.loads(QUEUE.read_text())
    except (OSError, ValueError):
        q = {}
    q.setdefault("paused", False)
    q.setdefault("next", 1)
    q.setdefault("jobs", [])
    return q


def update(fn):
    """Lee la cola, aplica fn(q) y la guarda de forma atómica; devuelve lo que devuelva fn."""
    with locked():
        q = load()
        result = fn(q)
        tmp = QUEUE.with_suffix(".tmp")
        tmp.write_text(json.dumps(q, ensure_ascii=False))
        os.replace(tmp, QUEUE)
        return result


def snapshot():
    with locked():
        return load()


def find(q, job_id):
    return next((j for j in q["jobs"] if j["id"] == job_id), None)


def free_name(out: Path):
    """No pisa un audio existente ni uno que ya esté en la cola: añade « (2)», « (3)»…"""
    taken = {j["out"] for j in snapshot()["jobs"] if j["status"] not in FINISHED}
    n, cand = 2, out
    while cand.exists() or str(cand) in taken:
        cand = out.with_name(f"{out.stem} ({n}){out.suffix}")
        n += 1
    return cand


# ---------------------------------------------------------------- operaciones

def add_job(src, out, voice=DEFAULT_VOICE, speed=1.0, text=None, title=None, overwrite=False):
    """Encola un archivo (o `text`, que se guarda aparte para que no cambie después). Devuelve el trabajo."""
    out = Path(out)
    if not overwrite:
        out = free_name(out)

    def _add(q):
        job_id = q["next"]
        q["next"] += 1
        path = Path(src) if src else None
        if text is not None:
            folder = TEXTS / str(job_id)
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / (out.stem + ".md")
            path.write_text(text, encoding="utf-8")
        job = {"id": job_id, "src": str(path), "out": str(out), "voice": voice, "speed": speed,
               "title": title or path.name, "status": "queued", "done": 0, "total": 0, "eta": None,
               "message": None, "duration": None, "chapters": None, "added": time.time()}
        q["jobs"].append(job)
        return job

    job = update(_add)
    ensure_daemon()
    return job


def add_rehacer(audio, n, texto=None):
    """Encola rehacer el fragmento n de un audio ya exportado (md2audio --rehacer)."""
    audio = Path(audio)
    mapa = json.loads(Path(audio.with_name(f".{audio.name}.juglar.json")).read_text())

    def _add(q):
        job_id = q["next"]
        q["next"] += 1
        args = [str(audio), "--rehacer", str(n), *(["--texto", texto] if texto else []), "--json"]
        job = {"id": job_id, "src": str(audio), "out": str(audio), "voice": mapa["voz"], "speed": mapa["velocidad"],
               "args": args, "title": f"{audio.name} · rehacer el trozo {n}", "status": "queued", "done": 0,
               "total": 0, "eta": None, "message": None, "duration": None, "chapters": None, "added": time.time()}
        q["jobs"].append(job)
        return job

    job = update(_add)
    ensure_daemon()
    return job


def extras_de(c):
    """bpm, tonalidad, compás y los campos de «cómo suena» de una canción (musica.leer_cancion), para add_musica."""
    import musica
    return {"bpm": c.get("bpm"), "clave": c.get("clave", ""), "compas": c.get("compas", ""),
            "campos": {k: c.get(k, "") for k in musica.CAMPOS}}


def add_cancion_md(path, salida=None):
    """Encola la canción descrita en un .md (título, «Estilo:», «Duración:»… y la letra; ver docs/GUIA.md §8)."""
    import musica
    c = musica.leer_cancion(path)
    if not c["descripcion"]:
        raise ValueError(f"«{Path(path).name}» no dice cómo suena: añade una línea «Estilo: …» bajo el título")
    out = salida or rutas.MUSICA / f"{musica.nombre_archivo(c['titulo'])}.mp3"
    return add_musica(out, c["descripcion"], c["letra"], c["duracion"] or 0,
                      -1 if c["semilla"] is None else c["semilla"], c["idioma"] or "es",
                      instrumental=c["instrumental"] or not c["letra"].strip(), titulo=c["titulo"],
                      **extras_de(c))


def add_actualizar(audio, nuevo):
    """Encola rehacer solo los trozos de un audio que cambiaron en su texto corregido (md2audio --actualizar)."""
    audio, nuevo = Path(audio), Path(nuevo).resolve()
    mapa = json.loads(Path(audio.with_name(f".{audio.name}.juglar.json")).read_text())

    def _add(q):
        job_id = q["next"]
        q["next"] += 1
        job = {"id": job_id, "src": str(audio), "out": str(audio), "voice": mapa["voz"], "speed": mapa["velocidad"],
               "args": [str(audio), "--actualizar", str(nuevo), "--json"],
               "title": f"{audio.name} · cambios de {nuevo.name}", "status": "queued", "done": 0, "total": 0,
               "eta": None, "message": None, "duration": None, "chapters": None, "added": time.time()}
        q["jobs"].append(job)
        return job

    job = update(_add)
    ensure_daemon()
    return job


def add_musica(salida, descripcion, letra="", duracion=0, semilla=-1, idioma="es", instrumental=False,
               titulo=None, overwrite=False, bpm=None, clave="", compas="", campos=None):
    """Encola generar una canción con ACE-Step (motores/musica_worker.py). Devuelve el trabajo."""
    if not rutas.ACESTEP_PY.exists():
        raise RuntimeError("ACE-Step no está instalado (vuelve a ejecutar install.sh y acepta la música)")
    import musica
    letra = musica.normalizar_letra(letra or "")
    out = Path(salida)
    if not overwrite:
        out = free_name(out)

    def _add(q):
        job_id = q["next"]
        q["next"] += 1
        folder = TEXTS / str(job_id)
        folder.mkdir(parents=True, exist_ok=True)
        pet = folder / "peticion.json"
        pet.write_text(json.dumps({"salida": str(out), "titulo": titulo or out.stem, "descripcion": descripcion,
                                   "letra": letra, "duracion": duracion, "semilla": semilla, "idioma": idioma,
                                   "instrumental": instrumental, "bpm": bpm, "clave": clave, "compas": compas,
                                   "campos": campos or {}},
                                  ensure_ascii=False), encoding="utf-8")
        job = {"id": job_id, "tipo": "musica", "src": str(pet), "out": str(out), "voice": "musica", "speed": 1.0,
               "cmd": [str(rutas.ACESTEP_PY), str(MUSICA_WORKER), str(pet)],
               "title": f"♪ {titulo or out.stem}", "status": "queued", "done": 0, "total": 0, "eta": None,
               "message": None, "duration": None, "chapters": None, "added": time.time()}
        q["jobs"].append(job)
        return job

    job = update(_add)
    ensure_daemon()
    return job


def _anotar(h, job, ev, cuando=None):
    out = str(Path(job["out"]).resolve())
    cuando = cuando or time.time()
    e = h.setdefault(out, {"audio": out, "creado": cuando, "rehechos": 0})
    if not job.get("args"):
        e["titulo"] = job["title"]
    e.update(voz=job["voice"], duracion=ev.get("duration"), capitulos=ev.get("chapters"), modificado=cuando)
    if job.get("args"):
        e["rehechos"] = e.get("rehechos", 0) + (ev.get("cambios") or 1)
    e["titulo"] = e.get("titulo") or Path(out).name
    e.setdefault("jobs", []).append(job["id"])


def _leer_historial():
    try:
        return json.loads(HISTORIAL.read_text())
    except (OSError, ValueError):
        return {}


def _guardar_historial(h):
    tmp = HISTORIAL.with_suffix(".tmp")
    tmp.write_text(json.dumps(h, ensure_ascii=False))
    os.replace(tmp, HISTORIAL)


def registrar(job, ev):
    """Anota en el historial un audio terminado (o que se le rehízo un trozo)."""
    with locked():
        h = _leer_historial()
        _anotar(h, job, ev)
        _guardar_historial(h)


def historial():
    """Audios exportados que siguen en la computadora, del más reciente al más antiguo (los borrados se olvidan).
    Los trabajos terminados de la cola que aún no estén anotados se añaden aquí."""
    with locked():
        h = _leer_historial()
        cambiado = False
        vistos = {j for e in h.values() for j in e.get("jobs", [])}
        for job in load()["jobs"]:
            if job.get("status") == "done" and job.get("tipo") != "musica" and job["id"] not in vistos:
                _anotar(h, job, job, job.get("started") or job.get("added"))
                cambiado = True
        vivos = {k: e for k, e in h.items() if Path(k).exists()}
        if cambiado or len(vivos) != len(h):
            _guardar_historial(vivos)
    return sorted(vivos.values(), key=lambda e: -e.get("modificado", 0))


def cancel_job(job_id):
    def _cancel(q):
        job = find(q, job_id)
        if not job:
            return
        if job["status"] == "queued":
            job["status"] = "cancelled"
            job["message"] = "Cancelado"
            cleanup_text(job)
        elif job["status"] == "running":
            job["cancel"] = True
    update(_cancel)


def remove_job(job_id):
    def _remove(q):
        q["jobs"] = [j for j in q["jobs"] if j["id"] != job_id or j["status"] == "running"]
    update(_remove)


def clear_finished():
    update(lambda q: q.update(jobs=[j for j in q["jobs"] if j["status"] not in FINISHED]))


def set_paused(paused):
    update(lambda q: q.update(paused=paused))
    if not paused:
        ensure_daemon()


def cleanup_text(job):
    if Path(job["src"]).is_relative_to(TEXTS):
        shutil.rmtree(Path(job["src"]).parent, ignore_errors=True)


def has_work(q=None):
    q = q or snapshot()
    return any(j["status"] in ("queued", "running") for j in q["jobs"])


# ---------------------------------------------------------------- proceso residente

def ensure_daemon():
    """Arranca el proceso residente si no hay uno (con systemd-run, para que no dependa de la ventana)."""
    STATE.mkdir(parents=True, exist_ok=True)
    with open(DAEMON_LOCK, "a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return  # ya hay uno
    cmd = [sys.executable, str(Path(__file__).resolve()), "daemon"]
    try:
        r = subprocess.run(["systemd-run", "--user", "--collect", "--quiet", "--unit=juglar-cola",
                            "--description=Cola de exportación de Juglar", *cmd], capture_output=True)
        if r.returncode == 0:
            return
    except OSError:
        pass
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


class Inhibitor:
    """Bloqueo de suspensión en logind mientras se convierte (la pantalla sí puede apagarse)."""

    def __init__(self):
        self.fd = None

    def acquire(self):
        if self.fd is not None:
            return
        try:
            from gi.repository import Gio, GLib
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM)
            res, fds = bus.call_with_unix_fd_list_sync(
                "org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager", "Inhibit",
                GLib.Variant("(ssss)", ("sleep", "Juglar", "Convirtiendo audio en cola", "block")),
                GLib.VariantType("(h)"), Gio.DBusCallFlags.NONE, -1, None, None)
            self.fd = fds.get(res.unpack()[0])
        except Exception as e:
            print(f"no se pudo bloquear la suspensión: {e}", file=sys.stderr)

    def release(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def _die_with_parent():
    os.setsid()
    _libc.prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG


def notify(title, body):
    try:
        subprocess.run(["notify-send", "-a", "Juglar", "-i", "audio-x-generic", title, body],
                       timeout=5, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass


def run_job(job, inhibit):
    """Ejecuta un trabajo hasta que termina, atendiendo pausa y cancelación. Devuelve su estado final."""
    log = open(LOG, "ab")
    tmp = STATE / "tmp" / str(job["id"])  # temporales propios: se borran aunque md2audio muera a la fuerza
    tmp.mkdir(parents=True, exist_ok=True)
    args = job.get("args") or [job["src"], "-o", job["out"], "-v", job["voice"], "-s", f"{job['speed']:.3f}", "--json"]
    proc = subprocess.Popen(
        job.get("cmd") or [str(VENV_PY), "-I", str(MD2AUDIO), *args],
        stdout=subprocess.PIPE, stderr=log, preexec_fn=_die_with_parent, env={**os.environ, "TMPDIR": str(tmp)})
    os.set_blocking(proc.stdout.fileno(), False)
    inhibit.acquire()
    buf, ev_done, error, progress = b"", None, None, None
    stopped = cancelled = False
    while True:
        ready, _, _ = select.select([proc.stdout], [], [], 1.0)
        if ready:
            try:
                data = os.read(proc.stdout.fileno(), 65536)
            except (BlockingIOError, OSError):
                data = b""
            buf += data
            *lines, buf = buf.split(b"\n")
            for line in lines:
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("type") == "progress":
                    progress = ev
                elif ev.get("type") == "done":
                    ev_done = ev
                elif ev.get("type") == "error":
                    error = ev.get("message")
        rc = proc.poll()

        def _tick(q):
            j = find(q, job["id"])
            if j is None:
                return None, True, q["paused"]
            if progress:
                j.update(done=progress["done"], total=progress["total"], eta=progress.get("eta"))
                if progress.get("fase"):
                    j["fase"] = progress["fase"]
            return j, bool(j.get("cancel")), q["paused"]

        _, want_cancel, paused = update(_tick)
        if rc is not None:
            break
        if want_cancel and not cancelled:
            cancelled = True
            for sig in (signal.SIGTERM, signal.SIGCONT):  # un grupo detenido no recibe SIGTERM hasta reanudarse
                try:
                    os.killpg(proc.pid, sig)
                except ProcessLookupError:
                    pass
            stopped = False
            cancelled_at = time.monotonic()
        elif cancelled and time.monotonic() - cancelled_at > 8:
            try:  # md2audio no terminó a tiempo (p. ej. atascado cerrando sus procesos): rematarlo
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        elif paused and not stopped and not cancelled:
            os.killpg(proc.pid, signal.SIGSTOP)
            stopped = True
            inhibit.release()  # en pausa el equipo puede suspenderse
        elif not paused and stopped:
            os.killpg(proc.pid, signal.SIGCONT)
            stopped = False
            inhibit.acquire()
    proc.stdout.close()
    inhibit.release()
    try:
        os.killpg(proc.pid, signal.SIGKILL)  # restos del grupo (ffmpeg, worker de Qwen)
    except ProcessLookupError:
        pass
    shutil.rmtree(tmp, ignore_errors=True)
    if rc == 0 and ev_done:
        return "done", ev_done, None
    if cancelled:
        return "cancelled", None, "Cancelado"
    return "failed", None, error or f"Error en la conversión (código {rc}); ver {LOG}"


def work_loop():
    inhibit = Inhibitor()
    while True:
        def _next(q):
            if q["paused"]:
                return None
            job = next((j for j in q["jobs"] if j["status"] == "queued"), None)
            if job:
                job.update(status="running", started=time.time(), done=0, total=0, eta=None)
            return job
        job = update(_next)
        if not job:
            return
        status, ev, message = run_job(job, inhibit)

        def _finish(q):
            j = find(q, job["id"])
            if j is None:
                return
            j.update(status=status, message=message, eta=None, cancel=False)
            if ev:
                j.update(duration=ev.get("duration"), chapters=ev.get("chapters"), done=j["total"],
                         revision=ev.get("revision"))
            if status != "done":
                j["done"] = 0
        update(_finish)
        cleanup_text(job)
        if status == "done" and job.get("tipo") == "musica":
            notify("Canción lista", Path(job["out"]).name)
        elif status == "done":
            registrar(job, ev or {})
            notify("Audio listo", Path(job["out"]).name)
        elif status == "failed":
            notify("No se pudo convertir", f"{job['title']}: {message}")


def daemon():
    lock = open(DAEMON_LOCK, "a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    # trabajos que se quedaron a medias (apagado, caída): volver a empezarlos
    def _recover(q):
        for j in q["jobs"]:
            if j["status"] == "running":
                j.update(status="queued", done=0, eta=None, cancel=False)
    update(_recover)
    while True:
        work_loop()
        fcntl.flock(lock, fcntl.LOCK_UN)
        q = snapshot()
        if q["paused"] or not has_work(q):
            return
        try:  # llegó trabajo justo al salir: seguir
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return


# ---------------------------------------------------------------- línea de órdenes

def fmt_time(sec):
    sec = int(sec or 0)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def describe(job, paused):
    st, pct = job["status"], job["done"] * 100 // max(job["total"], 1)
    if st == "queued":
        return "en cola"
    if st == "running":
        if paused:
            return f"en pausa ({pct} %)"
        eta = f", quedan ~{fmt_time(job['eta'])}" if job.get("eta") else ""
        fase = f" · {job['fase']}" if job.get("tipo") == "musica" and job.get("fase") else ""
        return f"{pct} %{eta}{fase}" if job["total"] else "preparando voz"
    if st == "done":
        return f"listo, {fmt_time(job['duration'])} de audio"
    return job.get("message") or ("cancelado" if st == "cancelled" else "error")


def main():
    ap = argparse.ArgumentParser(description="Cola de conversión de texto a audio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="añadir archivos .md/.txt a la cola")
    a.add_argument("files", nargs="+", type=Path)
    a.add_argument("-v", "--voice", default=DEFAULT_VOICE)
    a.add_argument("-s", "--speed", type=float, default=1.0)
    a.add_argument("-o", "--output", type=Path, help="archivo de salida (solo con un archivo)")
    a.add_argument("-f", "--format", default="mp3", help="mp3, ogg, m4b o wav (por defecto mp3)")
    a.add_argument("--overwrite", action="store_true", help="sobrescribir el audio si ya existe")
    lb = sub.add_parser("libro", help="añadir todos los capítulos de una carpeta (ver docs/GUIA.md, «Libros por carpetas»)")
    lb.add_argument("carpeta", type=Path)
    lb.add_argument("--todo", action="store_true", help="volver a exportar también los capítulos que ya tienen audio")
    lb.add_argument("-v", "--voice", help="narrador (si no, el de juglar.json o el por defecto)")
    lb.add_argument("-f", "--format", help="mp3, ogg, m4b o wav (si no, el de juglar.json o mp3)")
    rh = sub.add_parser("rehacer", help="volver a generar un trozo de un audio exportado (md2audio AUDIO --fragmentos los lista)")
    rh.add_argument("audio", type=Path)
    rh.add_argument("n", type=int, nargs="?", help="número del fragmento")
    rh.add_argument("--md", type=Path, help="texto corregido: rehace solo los trozos que cambiaron")
    rh.add_argument("--texto", help="texto nuevo para ese fragmento (por defecto, el mismo)")
    mu = sub.add_parser("musica", help="generar canciones con ACE-Step: archivos .md de canción (ver docs/GUIA.md §8) "
                                        "o -d DESCRIPCIÓN [--letra ARCHIVO]")
    mu.add_argument("canciones", nargs="*", type=Path, help="archivos .md de canción (título, Estilo:, letra…)")
    mu.add_argument("-d", "--descripcion", help="estilo, instrumentos, voz, ambiente… (manda sobre el del .md)")
    mu.add_argument("--letra", type=Path, help="archivo .txt/.md con la letra; sin letra = instrumental")
    mu.add_argument("-t", "--duracion", type=float, help="segundos (10-600); 0 = la que elija el modelo")
    mu.add_argument("--semilla", type=int)
    mu.add_argument("--idioma")
    mu.add_argument("-o", "--output", type=Path, help="archivo de salida (por defecto en ~/Música/Juglar)")
    ls = sub.add_parser("list", help="ver la cola")
    ls.add_argument("--json", action="store_true")
    for name, h in (("pause", "pausar la cola"), ("resume", "reanudar la cola"), ("clear", "quitar los terminados"),
                    ("daemon", "proceso residente (lo lanza la propia cola)")):
        sub.add_parser(name, help=h)
    for name, h in (("cancel", "cancelar un trabajo"), ("remove", "quitar un trabajo de la lista")):
        sub.add_parser(name, help=h).add_argument("id", type=int)
    args = ap.parse_args()

    if args.cmd == "add":
        if args.output and len(args.files) > 1:
            sys.exit("-o solo sirve con un archivo")
        for f in args.files:
            if not f.is_file():
                sys.exit(f"No existe: {f}")
            out = args.output or f.with_suffix("." + args.format.lstrip("."))
            job = add_job(f.resolve(), out.resolve(), args.voice, args.speed, overwrite=args.overwrite)
            print(f"#{job['id']} {f.name} → {Path(job['out']).name}")
    elif args.cmd == "libro":
        import libro
        try:
            lib = libro.Libro(args.carpeta)
        except ValueError as e:
            sys.exit(str(e))
        for cap, n, marca in (lib.marcas_desconocidas() if (args.voice or lib.narrador or DEFAULT_VOICE).startswith("qwen:") else []):
            print(f"Aviso: {cap.name}, línea {n}: —@{marca} no es ningún personaje ni voz", file=sys.stderr)
        voz, fmt = args.voice or lib.narrador or DEFAULT_VOICE, args.format or lib.formato
        hechos = 0
        for cap in lib.capitulos:
            out = lib.salida(cap, fmt)
            if out.exists() and not args.todo:
                print(f"ya tiene audio  {cap.name}")
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            job = add_job(cap.resolve(), out.resolve(), voz, lib.velocidad, title=f"{lib.titulo} · {cap.stem}",
                          overwrite=True)
            print(f"#{job['id']} {cap.name} → {out}")
            hechos += 1
        print(f"{hechos} capítulo(s) en la cola")
    elif args.cmd == "rehacer":
        if (args.n is None) == (args.md is None):
            sys.exit("Indica el número del trozo o --md con el texto corregido")
        try:
            job = (add_actualizar(args.audio.resolve(), args.md) if args.md
                   else add_rehacer(args.audio.resolve(), args.n, args.texto))
        except (OSError, ValueError):
            sys.exit("Ese audio no tiene mapa de fragmentos: vuelve a exportarlo con esta versión de Juglar")
        print(f"#{job['id']} {job['title']}")
    elif args.cmd == "musica":
        import musica
        archivos = list(args.canciones) + ([args.letra] if args.letra else [])
        if not archivos and not args.descripcion:
            sys.exit("Indica uno o más .md de canción, o -d «cómo suena»")
        if args.output and len(archivos) > 1:
            sys.exit("-o solo vale con una canción")
        for f in archivos or [None]:
            try:
                c = musica.leer_cancion(f) if f else musica.completar(
                    {**musica.nueva_cancion(args.output.stem if args.output else "Canción"), "instrumental": True})
            except (OSError, ValueError) as e:
                print(f"{f}: {e}", file=sys.stderr)
                continue
            if args.descripcion:  # -d sustituye al estilo (los demás campos del .md se quedan)
                c = musica.completar({**c, "estilo": args.descripcion})
            desc = c["descripcion"]
            if not desc:
                print(f"{f}: no dice cómo suena (añade «Estilo: …» bajo el título, o usa -d)", file=sys.stderr)
                continue
            out = args.output or rutas.MUSICA / f"{musica.nombre_archivo(c['titulo'])}.mp3"
            job = add_musica(out, desc, c["letra"], args.duracion if args.duracion is not None else (c["duracion"] or 0),
                             args.semilla if args.semilla is not None else (-1 if c["semilla"] is None else c["semilla"]),
                             args.idioma or c["idioma"] or "es", instrumental=c["instrumental"] or not c["letra"].strip(),
                             titulo=c["titulo"], **extras_de(c))
            print(f"#{job['id']}  {job['title']}  →  {job['out']}")
    elif args.cmd == "list":
        q = snapshot()
        if args.json:
            print(json.dumps(q, ensure_ascii=False))
            return
        print("COLA EN PAUSA" if q["paused"] else "Cola activa" if has_work(q) else "Cola vacía")
        for j in q["jobs"]:
            print(f"#{j['id']:<3} {j['title']:<40.40} {describe(j, q['paused'])}")
    elif args.cmd == "pause":
        set_paused(True)
        print("Cola en pausa")
    elif args.cmd == "resume":
        set_paused(False)
        print("Cola reanudada")
    elif args.cmd == "cancel":
        cancel_job(args.id)
    elif args.cmd == "remove":
        remove_job(args.id)
    elif args.cmd == "clear":
        clear_finished()
    elif args.cmd == "daemon":
        daemon()


if __name__ == "__main__":
    main()
