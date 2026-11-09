"""Shared helpers for Legend AI Edit scripts: tool paths, project layout, timebase."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# models (Whisper) live inside the project, not in ~/.cache: the toolkit carries its own dependencies.
# Must be set before huggingface_hub / mlx_whisper are imported.
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
# FFmpeg comes from the Brewfile (ffmpeg-full, keg-only); LAE_FFMPEG_BIN overrides the folder.
_FF_BIN = Path(os.environ.get("LAE_FFMPEG_BIN", "/opt/homebrew/opt/ffmpeg-full/bin"))
FFMPEG = str(_FF_BIN / "ffmpeg")
FFPROBE = str(_FF_BIN / "ffprobe")
MEDIA_EXTS = {".mp4", ".mov", ".mxf", ".m4v"}


# --- timebase -------------------------------------------------------------

def parse_rate(rate: str) -> Fraction:
    """'30000/1001' -> Fraction(30000, 1001). Never assume 30 for 29.97."""
    num, _, den = rate.partition("/")
    return Fraction(int(num), int(den or 1))


def seconds_to_frame(seconds: float | str | Fraction, rate: Fraction) -> int:
    """The single seconds -> frame conversion. Rounds to the nearest frame."""
    value = seconds if isinstance(seconds, Fraction) else Fraction(str(seconds))
    return round(value * rate)


def frame_to_seconds(frame: int, rate: Fraction) -> Fraction:
    return Fraction(frame) / rate


# --- project layout -------------------------------------------------------

def video_dir(arg: str) -> Path:
    path = Path(arg).expanduser().resolve()
    if not (path / "bruto").is_dir():
        sys.exit(f"error: {path} has no bruto/ folder")
    return path


def source_clips(vdir: Path) -> list[Path]:
    return sorted(p for p in (vdir / "bruto").iterdir()
                  if p.suffix.lower() in MEDIA_EXTS and not p.name.startswith("."))


def latest_inventory(vdir: Path) -> dict:
    """The newest trabalho/inventario[_vNN].json (versions are added when new clips arrive)."""
    files = sorted((vdir / "trabalho").glob("inventario*.json"),
                   key=lambda p: (p.stem != "inventario", p.stem))
    return json.loads(files[-1].read_text(encoding="utf-8"))


def probe(path: Path) -> dict:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def write_new(path: Path, text: str) -> None:
    """Write a text file without ever overwriting an existing one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(text)
