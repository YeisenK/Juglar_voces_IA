#!/usr/bin/env bash
# Instala Juglar para el usuario actual (no necesita root salvo para los paquetes del sistema).
#
#   ./install.sh               todo: Piper, Kokoro, Qwen3-TTS (GPU) y Whisper
#   SIN_QWEN=1 ./install.sh    solo las voces rápidas (Piper y Kokoro), sin GPU
#   CON_MUSICA=1 ./install.sh  además, la música (ACE-Step 1.5, ~23 GB con modelos); si no, lo pregunta
#
# Es seguro volver a ejecutarlo: lo que ya está instalado se deja como está, salvo las voces que cambiaron
# en el repositorio, que se actualizan guardando copia (ACTUALIZAR_VOCES=1 / =0 para no preguntar).
set -euo pipefail

R="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
DATA="${JUGLAR_DATA:-${XDG_DATA_HOME:-$HOME/.local/share}/juglar}"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/juglar"
BIN="$HOME/.local/bin"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
PY=3.12

paso() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
aviso() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
descargar() {  # descargar URL DESTINO (solo si falta)
  [[ -s "$2" ]] && return 0
  mkdir -p "$(dirname "$2")"
  curl -fL --progress-bar -o "$2.part" "$1" && mv "$2.part" "$2"
}

# ---------------------------------------------------------------- 1. requisitos del sistema
paso "Comprobando los requisitos del sistema"
falta=()
command -v ffmpeg >/dev/null || falta+=(ffmpeg)
command -v aplay >/dev/null || falta+=(alsa-utils)
command -v curl >/dev/null || falta+=(curl)
/usr/bin/python3 -c 'import gi; gi.require_version("Gtk","4.0"); gi.require_version("Adw","1"); from gi.repository import Adw' \
  2>/dev/null || falta+=(python3-gobject gtk4 libadwaita)
if /usr/bin/python3 -c 'import gi; gi.require_version("Adw","1"); from gi.repository import Adw; exit(Adw.get_minor_version() >= 7)' 2>/dev/null; then
  aviso "Juglar necesita libadwaita 1.7 o posterior; actualiza el sistema."
  exit 1
fi
if ((${#falta[@]})); then
  aviso "Faltan paquetes del sistema: ${falta[*]}"
  echo "    Fedora:        sudo dnf install ${falta[*]}"
  echo "    Debian/Ubuntu: sudo apt install ffmpeg alsa-utils curl python3-gi gir1.2-gtk-4.0 gir1.2-adw-1"
  exit 1
fi
if ! command -v uv >/dev/null; then
  paso "Instalando uv (gestor de entornos de Python)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
mkdir -p "$DATA" "$CONFIG" "$BIN" "$APPS" "$ICONS"

# ---------------------------------------------------------------- 2. entornos de Python
entorno() {  # entorno NOMBRE "paquetes..." [opciones de uv venv]
  local nombre="$1" dir="$DATA/$1" pkgs="$2"; shift 2
  if [[ -x "$dir/bin/python" ]]; then
    echo "    $nombre: ya existe"
    return 0
  fi
  paso "Creando el entorno «$nombre»"
  uv venv --python "$PY" "$@" "$dir"
  # shellcheck disable=SC2086
  uv pip install --python "$dir/bin/python" $pkgs
}

paso "Entornos de Python en $DATA"
entorno venv "piper-tts onnxruntime-gpu[cuda,cudnn] kokoro-onnx numpy"
if [[ -z "${SIN_QWEN:-}" ]]; then
  if ! command -v nvidia-smi >/dev/null; then
    aviso "No veo una tarjeta NVIDIA (nvidia-smi). Qwen3-TTS necesita una GPU con ~8 GB; usa SIN_QWEN=1 para omitirlo."
  fi
  # --managed-python: Qwen compila con triton y necesita las cabeceras de Python que trae uv
  entorno qwen "qwen-tts soundfile huggingface_hub" --managed-python
  entorno whisper "faster-whisper jiwer soundfile nvidia-cublas-cu12 nvidia-cudnn-cu12"
fi

# ---------------------------------------------------------------- 3. modelos
paso "Voces de Piper"
PV="https://huggingface.co/rhasspy/piper-voices/resolve/main/es"
for v in es_MX/claude/high/es_MX-claude-high es_ES/davefx/medium/es_ES-davefx-medium es_AR/daniela/high/es_AR-daniela-high; do
  n="$(basename "$v")"
  descargar "$PV/$v.onnx" "$DATA/piper-voces/$n.onnx"
  descargar "$PV/$v.onnx.json" "$DATA/piper-voces/$n.onnx.json"
done

paso "Modelo de Kokoro"
KV="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
descargar "$KV/kokoro-v1.0.onnx" "$DATA/kokoro/kokoro-v1.0.onnx"
descargar "$KV/voices-v1.0.bin" "$DATA/kokoro/voices-v1.0.bin"

if [[ -z "${SIN_QWEN:-}" ]]; then
  paso "Modelos de Qwen3-TTS y Whisper (unos 9 GB la primera vez)"
  "$DATA/qwen/bin/python" -c '
from huggingface_hub import snapshot_download
for m in ("Qwen/Qwen3-TTS-12Hz-1.7B-Base", "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"):
    print("   ", m); snapshot_download(m)'
  "$DATA/whisper/bin/python" -c '
from faster_whisper import WhisperModel
print("    large-v3-turbo"); WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")'
fi

# ---------------------------------------------------------------- 3b. música (opcional): ACE-Step 1.5
ACESTEP_REPO="https://github.com/ACE-Step/ACE-Step-1.5.git"
ACESTEP_VERSION="ca1e85f"   # la versión con la que se probó Juglar
if [[ -x "$DATA/acestep/.venv/bin/python" ]]; then
  musica=0   # ya está: no se toca
elif [[ -n "${CON_MUSICA:-}" ]]; then
  musica="$CON_MUSICA"
elif [[ -t 0 && -z "${SIN_QWEN:-}" ]]; then
  read -r -p "¿Instalar también la música (canciones con ACE-Step, unos 23 GB)? [s/N] " r </dev/tty || r=""
  [[ "$r" =~ ^[sSyY] ]] && musica=1 || musica=0
else
  musica=0
fi
if [[ "$musica" == 1 ]]; then
  paso "Música: ACE-Step 1.5 en $DATA/acestep (los modelos, ~15 GB, se bajan al generar la primera canción)"
  [[ -d "$DATA/acestep/.git" ]] || git clone "$ACESTEP_REPO" "$DATA/acestep"
  git -C "$DATA/acestep" checkout -q "$ACESTEP_VERSION" || aviso "No se pudo fijar la versión $ACESTEP_VERSION; se usa la última"
  (cd "$DATA/acestep" && UV_PYTHON=$PY uv sync)
fi

# ---------------------------------------------------------------- 4. voces de Qwen y ajustes
paso "Voces de Qwen incluidas"
mkdir -p "$DATA/voces"
# Copia las voces nuevas y actualiza las que cambiaron en el repositorio. voces/.repo.json recuerda qué versión
# de cada voz instaló Juglar: si la tuya sigue siendo esa, se actualiza sola; si no se sabe (instalaciones
# anteriores) o la cambiaste tú, pregunta (o ACTUALIZAR_VOCES=1 / =0). Antes de cambiar una voz se guarda una
# copia en voces_antes_FECHA, y se conservan tus ajustes (ajustes.json) y el nombre que le hayas puesto.
interactivo=0; [[ -t 0 ]] && interactivo=1
REPO="$R" DATA="$DATA" ACTUALIZAR="${ACTUALIZAR_VOCES:-}" INTERACTIVO="$interactivo" python3 - <<'EOF'
import datetime, hashlib, json, os, shutil
from pathlib import Path
repo, data = Path(os.environ["REPO"]) / "voces", Path(os.environ["DATA"]) / "voces"
reg_path = data / ".repo.json"
try:
    reg = json.loads(reg_path.read_text())
except (OSError, ValueError):
    reg = {}
h = lambda f: hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None  # noqa: E731
copia = data.parent / f"voces_antes_{datetime.date.today()}"

def actualizar(n):
    src, dst = repo / n, data / n
    if dst.exists():
        if not (copia / n).exists():
            shutil.copytree(dst, copia / n)
        try:
            nombre = json.loads((dst / "meta.json").read_text()).get("nombre")
        except (OSError, ValueError):
            nombre = None
        for f in ("ref.wav", "ref.txt", "meta.json"):
            shutil.copy(src / f, dst / f)
        if nombre:  # el nombre que le puso el usuario se queda
            meta = json.loads((dst / "meta.json").read_text())
            meta["nombre"] = nombre
            (dst / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    else:
        shutil.copytree(src, dst)
    reg[n] = h(src / "ref.wav")

nuevas, actualizadas, dudosas = [], [], []
for src in sorted(p for p in repo.iterdir() if (p / "ref.wav").exists()):
    n, nuevo, tuyo = src.name, h(src / "ref.wav"), h(data / src.name / "ref.wav")
    if tuyo is None:
        actualizar(n); nuevas.append(n)
    elif tuyo == nuevo:
        reg[n] = nuevo
    elif reg.get(n) == tuyo:  # no la tocaste desde que se instaló: se actualiza
        actualizar(n); actualizadas.append(n)
    else:
        dudosas.append(n)

if dudosas:
    print(f"    {len(dudosas)} voces son distintas de las del repositorio (cambiaron en Juglar, o las cambiaste tú):")
    print("      " + ", ".join(dudosas))
    resp = os.environ["ACTUALIZAR"]
    if not resp and os.environ["INTERACTIVO"] == "1":
        try:  # el código de este script llega por stdin: la respuesta se lee del terminal
            with open("/dev/tty") as tty:
                print("    ¿Cambiarlas por las del repositorio? Se guarda una copia de las tuyas [s/N] ", end="", flush=True)
                resp = tty.readline()
        except OSError:
            resp = ""
    if resp.strip().lower() in ("s", "si", "sí", "y", "1"):
        for n in dudosas:
            actualizar(n)
        actualizadas += dudosas
    else:
        print("    Se dejan como están (para cambiarlas: ACTUALIZAR_VOCES=1 ./install.sh)")

reg_path.write_text(json.dumps(reg, indent=1))
total = sum(1 for p in data.iterdir() if p.is_dir())
print(f"    {len(nuevas)} voces nuevas y {len(actualizadas)} actualizadas ({total} en total)")
if actualizadas:
    print(f"    Copia de las que se cambiaron en {copia}")
EOF
[[ -e "$CONFIG/pronunciacion.txt" ]] || cp "$R/juglar/pronunciacion.txt" "$CONFIG/pronunciacion.txt"
[[ -e "$CONFIG/prueba_voz.txt" ]] || cp "$R/juglar/prueba_voz.txt" "$CONFIG/prueba_voz.txt"

# ---------------------------------------------------------------- 5. lanzadores
paso "Comandos y lanzador del escritorio"
for b in juglar leer md2audio juglar-cola juglar-pruebas; do
  ln -sf "$R/bin/$b" "$BIN/$b"
done
for f in io.github.yeisenk.Juglar io.github.yeisenk.Juglar.Leer; do
  sed "s#@BIN@#$BIN#g" "$R/data/$f.desktop.in" > "$APPS/$f.desktop"
done
cp "$R/data/io.github.yeisenk.Juglar.svg" "$ICONS/"
update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -f -t "${ICONS%/scalable/apps}" 2>/dev/null || true
case ":$PATH:" in *":$BIN:"*) ;; *) aviso "Añade $BIN a tu PATH para usar los comandos desde la terminal." ;; esac

paso "Listo"
echo "    Abre «Juglar» desde el menú de aplicaciones o escribe: juglar"
echo "    Guía para escribir tus textos: $R/docs/GUIA.md"
[[ -z "${SIN_QWEN:-}" ]] && echo "    Opcional: «juglar-pruebas» genera ya las pruebas de todas las voces (tarda unos minutos)."
exit 0
