#!/usr/bin/env bash
# Instala Juglar para el usuario actual (no necesita root salvo para los paquetes del sistema).
#
#   ./install.sh               todo: Piper, Kokoro, Qwen3-TTS (GPU) y Whisper
#   SIN_QWEN=1 ./install.sh    solo las voces rápidas (Piper y Kokoro), sin GPU
#
# Es seguro volver a ejecutarlo: lo que ya está instalado se deja como está.
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

# ---------------------------------------------------------------- 4. voces de Qwen y ajustes
paso "Voces de Qwen incluidas"
mkdir -p "$DATA/voces"
nuevas=0
for d in "$R"/voces/*/; do
  n="$(basename "$d")"
  if [[ ! -e "$DATA/voces/$n" ]]; then cp -r "$d" "$DATA/voces/$n"; nuevas=$((nuevas + 1)); fi
done
echo "    $nuevas voces nuevas copiadas ($(ls "$DATA/voces" | wc -l) en total)"
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
