"""Inventory the source clips of one video: python scripts/inventory.py videos/<date>_<name>

Writes trabalho/inventario.json (never overwrites; pass --version to add _v02 etc.).
"""
from __future__ import annotations

import argparse
import json
from fractions import Fraction

import lae


def describe(path) -> dict:
    info = lae.probe(path)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    rate = lae.parse_rate(video["r_frame_rate"])
    duration = Fraction(info["format"]["duration"])
    tags = video.get("tags", {})
    return {
        "file": path.name,
        "size_bytes": path.stat().st_size,
        "duration_s": float(duration),
        "frames": int(video.get("nb_frames") or lae.seconds_to_frame(duration, rate)),
        "rate": video["r_frame_rate"],
        "fps": round(float(rate), 3),
        "width": video["width"],
        "height": video["height"],
        "codec": video["codec_name"],
        "pix_fmt": video.get("pix_fmt"),
        "color_tags": {k: video.get(k) for k in ("color_primaries", "color_transfer", "color_space", "color_range")},
        "bit_rate": int(video.get("bit_rate", 0)),
        "timecode": tags.get("timecode"),
        "creation_time": tags.get("creation_time"),
        "audio": [{"index": a["index"], "codec": a["codec_name"], "sample_rate": int(a["sample_rate"]),
                   "channels": a["channels"]} for a in audio],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir")
    ap.add_argument("--version", default="")
    args = ap.parse_args()
    vdir = lae.video_dir(args.video_dir)

    clips = [describe(p) for p in lae.source_clips(vdir)]
    rates = sorted({c["rate"] for c in clips})
    sizes = sorted({f'{c["width"]}x{c["height"]}' for c in clips})
    report = {
        "video": vdir.name,
        "clips": clips,
        "summary": {
            "count": len(clips),
            "total_duration_s": round(sum(c["duration_s"] for c in clips), 3),
            "total_bytes": sum(c["size_bytes"] for c in clips),
            "rates": rates,
            "resolutions": sizes,
            "mixed_rates": len(rates) > 1,
        },
    }
    suffix = f"_{args.version}" if args.version else ""
    out = vdir / "trabalho" / f"inventario{suffix}.json"
    lae.write_new(out, json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    s = report["summary"]
    print(f"{s['count']} clips, {s['total_duration_s'] / 60:.1f} min, {s['total_bytes'] / 1e9:.1f} GB, "
          f"rates={rates}, resolutions={sizes}")
    if s["mixed_rates"]:
        print("WARNING: mixed frame rates")
    print(f"wrote {out.relative_to(lae.ROOT)}")


if __name__ == "__main__":
    main()
