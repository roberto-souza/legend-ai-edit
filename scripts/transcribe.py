"""Transcribe source clips with word timestamps (mlx-whisper, local).

    .venv/bin/python scripts/transcribe.py videos/<date>_<name>

Output: trabalho/transcricao/<stem>.json with segments and per-word start/end in seconds
(relative to the clip start). Existing transcripts are skipped, never overwritten.
"""
from __future__ import annotations

import argparse
import json
import subprocess

import lae  # first: points HF_HOME at the project's model cache

import numpy as np
import mlx_whisper

MODEL = "mlx-community/whisper-large-v3-turbo"
SAMPLE_RATE = 16000


def load_audio(path) -> np.ndarray:
    # decode with ffmpeg-full so mlx-whisper never depends on the PATH ffmpeg
    raw = subprocess.run(
        [lae.FFMPEG, "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0",
         "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"],
        check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def transcribe(path, language: str) -> dict:
    result = mlx_whisper.transcribe(
        load_audio(path), path_or_hf_repo=MODEL, language=language,
        word_timestamps=True, condition_on_previous_text=False, verbose=None)
    segments = [{
        "start": round(s["start"], 3), "end": round(s["end"], 3), "text": s["text"].strip(),
        "no_speech_prob": round(s.get("no_speech_prob", 0.0), 3),
        "words": [{"word": w["word"].strip(), "start": round(w["start"], 3), "end": round(w["end"], 3),
                   "probability": round(w.get("probability", 0.0), 3)} for w in s.get("words", [])],
    } for s in result["segments"]]
    return {"file": path.name, "model": MODEL, "language": language,
            "text": result["text"].strip(), "segments": segments}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir")
    ap.add_argument("--language", default="pt")
    args = ap.parse_args()
    vdir = lae.video_dir(args.video_dir)
    outdir = vdir / "trabalho" / "transcricao"

    for src in lae.source_clips(vdir):
        out = outdir / f"{src.stem}.json"
        if out.exists():
            print(f"skip {out.name} (exists)")
            continue
        print(f"transcribe {src.name}", flush=True)
        data = transcribe(src, args.language)
        words = [w for s in data["segments"] for w in s["words"]]
        bad = [w for w in words if not w["end"] > w["start"]]
        lae.write_new(out, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(f"  {len(words)} words, {len(bad)} without own start/end", flush=True)


if __name__ == "__main__":
    main()
