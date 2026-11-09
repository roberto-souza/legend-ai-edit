"""Free disk space in a finished video folder. Sends files to the macOS Trash (recoverable).

    .venv/bin/python scripts/limpar.py videos/<pasta> --versoes --proxies --motion            # dry run
    .venv/bin/python scripts/limpar.py videos/<pasta> --versoes --proxies --motion --aplicar  # do it

  --versoes   old renders in final/: every rascunho_vNN and acabamento_vNN, and every final vNN
              except the newest one (the approved delivery stays)
  --proxies   trabalho/proxies/ (make_proxies.py recreates them; the timeline editor needs them)
  --motion    trabalho/motion/ (HyperFrames overlays; finish.py re-renders them on demand)

Never touches bruto/, assets/, the text files in trabalho/ (transcripts, plans, timelines, EDLs)
or the newest final render.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

import lae

TRASH = "/usr/bin/trash"


def size(paths: list[Path]) -> int:
    total = 0
    for p in paths:
        total += sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir")
    ap.add_argument("--versoes", action="store_true")
    ap.add_argument("--proxies", action="store_true")
    ap.add_argument("--motion", action="store_true")
    ap.add_argument("--aplicar", action="store_true", help="send to the Trash (default: only list)")
    args = ap.parse_args()
    vdir = lae.video_dir(args.video_dir)

    targets: list[Path] = []
    keep = None
    if args.versoes:
        finals = sorted((p for p in (vdir / "final").glob(f"{vdir.name}_v*.mp4") if re.search(r"_v\d+\.mp4$", p.name)),
                        key=lambda p: int(re.search(r"_v(\d+)\.mp4$", p.name).group(1)))
        keep = finals[-1] if finals else None
        targets += [p for p in finals if p != keep]
        targets += sorted((vdir / "final").glob(f"{vdir.name}_rascunho_v*.mp4"))
        targets += sorted((vdir / "final").glob(f"{vdir.name}_acabamento_v*.mp4"))
    if args.proxies and (vdir / "trabalho" / "proxies").exists():
        targets.append(vdir / "trabalho" / "proxies")
    if args.motion and (vdir / "trabalho" / "motion").exists():
        targets.append(vdir / "trabalho" / "motion")

    # safety net: nothing outside final/, trabalho/proxies, trabalho/motion
    allowed = [vdir / "final", vdir / "trabalho" / "proxies", vdir / "trabalho" / "motion"]
    for t in targets:
        if not any(t == a or a in t.parents for a in allowed):
            raise SystemExit(f"error: refusing to touch {t}")

    for t in targets:
        print(f"{size([t]) / 1e9:6.2f} GB  {t.relative_to(vdir)}")
    if keep:
        print(f"  fica:    {keep.relative_to(vdir)}")
    print(f"total {size(targets) / 1e9:.2f} GB")
    if not args.aplicar:
        print("simulação: nada foi mexido (use --aplicar para mandar para a Lixeira)")
        return
    if targets:
        subprocess.run([TRASH, *map(str, targets)], check=True)
    print("na Lixeira (recuperável até esvaziar)")


if __name__ == "__main__":
    main()
