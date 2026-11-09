"""Motion graphics rendered with HyperFrames (HTML/CSS/GSAP -> video with alpha).

Templates live in motion/<name>/ (one HyperFrames project each, text passed as variables).
Renders are cached in videos/<pasta>/trabalho/motion/ by template + variables + resolution,
so a title is rendered once and reused by every preview and the final render.

    .venv/bin/python scripts/motion.py videos/<pasta> titulo '{"titulo": "TARDE DE GRAVAÇÃO"}' [--4k]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import lae

MOTION = lae.ROOT / "motion"
HF_BIN = MOTION / "node_modules" / ".bin" / "hyperframes"
RATE = "30000/1001"


def available(template: str = "titulo") -> bool:
    return HF_BIN.exists() and (MOTION / template / "index.html").exists()


def render(vdir: Path, template: str, variables: dict, height: int) -> Path:
    """Render (or reuse) one overlay. Returns the MOV path (ProRes 4444 with alpha)."""
    src = (MOTION / template / "index.html").read_bytes()
    key = hashlib.sha1(src + json.dumps(variables, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:10]
    res = "landscape-4k" if height >= 2160 else "landscape"
    out = vdir / "trabalho" / "motion" / f"{template}_{key}_{height}p.mov"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".partial.mov")
    tmp.unlink(missing_ok=True)
    env = {**os.environ, "PUPPETEER_CACHE_DIR": str(lae.ROOT / ".cache" / "puppeteer"), "HYPERFRAMES_SKIP_SKILLS": "1"}
    subprocess.run([str(HF_BIN), "render", str(MOTION / template), "--variables", json.dumps(variables, ensure_ascii=False),
                    "--format", "mov", "--fps", RATE, "--resolution", res, "--quality", "delivery",
                    "--quiet", "--output", str(tmp)], check=True, env=env, cwd=MOTION)
    tmp.rename(out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir")
    ap.add_argument("template")
    ap.add_argument("variables")
    ap.add_argument("--4k", dest="uhd", action="store_true")
    args = ap.parse_args()
    path = render(lae.video_dir(args.video_dir), args.template, json.loads(args.variables), 2160 if args.uhd else 1080)
    info = lae.probe(path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    print(f"{path.relative_to(lae.ROOT)}  {v['width']}x{v['height']} {v.get('pix_fmt')} {v.get('nb_frames')} frames")


if __name__ == "__main__":
    main()
