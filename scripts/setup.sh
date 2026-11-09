#!/bin/zsh
# Prepara o Legend AI Edit numa máquina nova (ou confere uma que já existe). Seguro rodar de novo.
# Instala: ffmpeg-full e uv (Brewfile), o ambiente Python (.venv via uv), o modelo do Whisper
# (.cache/, uns 1,5 GB) e as dependências de motion (motion/node_modules, se a pasta existir).
set -e
cd "${0:A:h}/.."
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || { echo "Precisa de macOS com Apple Silicon."; exit 1; }
command -v brew >/dev/null || { echo "Instale o Homebrew primeiro: https://brew.sh"; exit 1; }

echo "→ Dependências de sistema (Brewfile)"
brew bundle --file=Brewfile

echo "→ Ambiente Python"
uv sync

echo "→ Modelo do Whisper em .cache/huggingface"
.venv/bin/python -c "
import sys; sys.path.insert(0, 'scripts'); import lae
from huggingface_hub import snapshot_download
print(snapshot_download('mlx-community/whisper-large-v3-turbo'))"

if [[ -f motion/package.json ]]; then
  echo "→ Motion (Remotion)"
  command -v node >/dev/null || { echo "Instale o Node.js 22 ou mais novo (nvm, fnm ou volta)."; exit 1; }
  [[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 22 ]] || { echo "Node.js 22 ou mais novo é necessário."; exit 1; }
  (cd motion && npm ci --no-audit --no-fund)
fi

echo "→ Conferência"
F=/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg
$F -hide_banner -filters | grep -qE ' subtitles ' && $F -hide_banner -filters | grep -qE ' lut3d ' && echo "FFmpeg ok (subtitles, lut3d)"
echo "Pronto. Editor: scripts/editor.sh"
