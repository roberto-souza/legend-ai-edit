"""Make 1080p preview proxies with the camera LUT applied.

    python scripts/make_proxies.py videos/<date>_<name> --lut luts/<camera>.cube

Output: trabalho/proxies/<stem>_proxy.mp4. Same frame rate and frame count as the source.
Existing proxies are skipped, never overwritten.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import lae


def lut_filter_path(path: Path) -> str:
    # escape for the ffmpeg filtergraph parser
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def frame_count(path: Path) -> int:
    out = subprocess.run(
        [lae.FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_packets",
         "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True).stdout
    # ffprobe 9 also lists stream_groups, repeating the same stream: take the first value
    return int(next(line for line in out.split() if line.strip()))


def make_proxy(src: Path, dst: Path, lut: Path, height: int, bitrate: str) -> None:
    vf = (f"scale=-2:{height}:flags=lanczos,format=rgb48le,"
          f"lut3d=file='{lut_filter_path(lut)}':interp=tetrahedral,format=yuv420p")
    tmp = dst.with_name(dst.stem + ".partial.mp4")
    tmp.unlink(missing_ok=True)
    cmd = [lae.FFMPEG, "-hide_banner", "-loglevel", "error", "-stats",
           "-hwaccel", "videotoolbox", "-i", str(src),
           "-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "0",
           "-vf", vf, "-fps_mode", "passthrough",
           "-c:v", "h264_videotoolbox", "-b:v", bitrate, "-profile:v", "high",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)]
    subprocess.run(cmd, check=True)
    tmp.rename(dst)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir")
    ap.add_argument("--lut", required=True)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--bitrate", default="10M")
    args = ap.parse_args()
    vdir = lae.video_dir(args.video_dir)
    lut = (lae.ROOT / args.lut).resolve() if not Path(args.lut).is_absolute() else Path(args.lut)
    if not lut.is_file():
        raise SystemExit(f"error: LUT not found: {lut}")

    outdir = vdir / "trabalho" / "proxies"
    outdir.mkdir(parents=True, exist_ok=True)
    for src in lae.source_clips(vdir):
        dst = outdir / f"{src.stem}_proxy.mp4"
        if dst.exists():
            print(f"skip {dst.name} (exists)")
            continue
        print(f"proxy {src.name}", flush=True)
        make_proxy(src, dst, lut, args.height, args.bitrate)
        a, b = frame_count(src), frame_count(dst)
        status = "ok" if a == b else f"FRAME MISMATCH source={a} proxy={b}"
        print(f"  {dst.name}: {b} frames, {status}", flush=True)


if __name__ == "__main__":
    main()
