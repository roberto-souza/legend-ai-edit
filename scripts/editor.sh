#!/bin/zsh
# Abre o editor de linha do tempo. Sem argumento, usa o vídeo mais recente em videos/.
set -e
cd "${0:A:h}/.."
VIDEO="${1:-$(ls -d videos/*/ | sort | tail -1)}"
PORT="${PORT:-8765}"
if curl -s -o /dev/null "http://127.0.0.1:$PORT/api/render"; then
  echo "Editor já está rodando: http://127.0.0.1:$PORT"
else
  echo "Abrindo o editor de ${VIDEO%/} em http://127.0.0.1:$PORT"
  (sleep 1; open "http://127.0.0.1:$PORT") &
  exec .venv/bin/python scripts/timeline_server.py "${VIDEO%/}" --port "$PORT"
fi
