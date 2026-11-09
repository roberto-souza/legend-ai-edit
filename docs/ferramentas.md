# Ferramentas

- FFmpeg: `ffmpeg-full` do `Brewfile`, em `/opt/homebrew/opt/ffmpeg-full/bin/`. `LAE_FFMPEG_BIN` troca a pasta. O `ffmpeg` do PATH não tem `subtitles` (libass).
- Transcrição: `.venv/bin/python` com `mlx_whisper` (`pyproject.toml`), modelo `mlx-community/whisper-large-v3-turbo` em `.cache/huggingface`. O `lae.py` define `HF_HOME`; importe `lae` antes de `mlx_whisper`. Parâmetros: `language="pt"`, `word_timestamps=True`.
- LUT da Osmo Pocket 4 (D-Log → Rec.709): `luts/osmo-pocket-4_dlog-to-rec709.cube`.
- Música e SFX: MCP `epidemic-sound` (`.mcp.json`); biblioteca local em `sfx/INDEX.md`.
- Scripts em `scripts/`. Rode com `.venv/bin/python scripts/<nome>.py`. `lae.py` concentra os caminhos e a conversão de tempo.
- ffprobe 9 também lista `stream_groups` e repete as faixas na saída. Leia `streams` e ignore as repetições.
- O Whisper estica o fim de cada palavra até o começo da próxima. Para achar pausas e bordas de corte, use `silencedetect` no áudio, não os tempos das palavras.
- Loudness: `loudnorm` sobe trechos baixos, como b-roll só com música, mesmo com `linear=true` quando o pico atrapalha. Por isso o `finish.py` nivela a voz por trecho, mede a mixagem e aplica um ganho fixo com `alimiter`.
- Epidemic Sound: as ferramentas do MCP se chamam `mcp__51a3f068-…__SearchRecordings`, `SearchSoundEffects`, `DownloadRecording` e `DownloadSoundEffect`. O link de download é assinado e expira; baixe com `curl` logo depois de pedir.
- Efeitos sonoros do Epidemic chegam baixos (-24 a -29 LUFS) e muitos crescem até o pico perto do fim. O `finish.py` nivela cada um em -16 LUFS; use `antes_s` para o pico cair no corte.
- Zoom animado: `scale` com `eval=frame` seguido de `crop` central, que é contínuo e rápido. O `zoompan` treme em vídeo.
