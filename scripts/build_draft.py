"""Build a rough cut from the proxies following a resolved cut plan.

    python scripts/build_draft.py videos/<date>_<name> trabalho/plano_v02.resolvido.json

Steps:
1. Split every span at silences longer than --max-pause (silencedetect on the audio),
   keeping a short breath on each side. Spans marked to_end (`+fim`) keep their pauses.
2. Cut each piece from the proxy at exact frames and the matching audio samples, with 10 ms
   audio fades at every cut, then concatenate.
3. Lay `apoio` clips (picture only) over the start of the span they belong to.
4. Every shot is fitted to 1920x1080. Vertical clips sit centred over a blurred, enlarged copy
   of themselves. `broll` spans are picture only (silence under them; music comes later).
   `efeito glitch_pb` turns the rest of its span black and white, opening with a short glitch.

Writes final/<name>_rascunho_vNN.mp4 and trabalho/rascunho_vNN.edl.json. Never overwrites:
the version number is the next free one.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import lae

SAMPLE_RATE = 48000
PAD_IN = Fraction("0.10")
PAD_OUT = Fraction("0.15")
FADE = 0.01
W, H = 1920, 1080
GLITCH_FRAMES = 8


def fit_filter(vertical: bool, tag: str) -> str:
    """Filter chain that turns one shot into a 1920x1080 frame (tag keeps pad labels unique)."""
    if not vertical:
        return f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    return (f"split[bg{tag}][fg{tag}];[bg{tag}]scale={W}:-2,crop={W}:{H},boxblur=30:3,eq=brightness=-0.08[bgb{tag}];"
            f"[fg{tag}]scale=-2:{H}[fgs{tag}];[bgb{tag}][fgs{tag}]overlay=(W-w)/2:0,setsar=1")


def glitch_pb_filter(scale: int = 1) -> str:
    """A few colour frames of RGB split and noise, then black and white.
    scale multiplies the pixel shifts (2 for 4K, so the glitch looks the same as on 1080p)."""
    g, k = GLITCH_FRAMES, scale
    return (f"rgbashift=rh={-24 * k}:bh={24 * k}:enable='lt(n,{g // 2})',"
            f"rgbashift=rh={16 * k}:gv={10 * k}:bv={-10 * k}:enable='between(n,{g // 2},{g - 1})',"
            f"noise=alls=60:allf=t:enable='lt(n,{g})',"
            f"eq=brightness=0.25:enable='eq(n,1)+eq(n,{g - 2})',"
            f"hue=s=0:enable='gte(n,{g})'")


def frac(x) -> Fraction:
    return Fraction(str(x))


_silences: dict[tuple[str, str, str], list[tuple[Fraction, Fraction]]] = {}


def silences(proxy: Path, max_pause: Fraction, noise: str) -> list[tuple[Fraction, Fraction]]:
    """Silent stretches longer than max_pause, measured on the audio itself.
    Whisper word ends stretch over pauses, so word timing alone cannot find them."""
    key = (str(proxy), str(max_pause), noise)
    if key not in _silences:
        log = subprocess.run(
            [lae.FFMPEG, "-hide_banner", "-nostats", "-i", str(proxy), "-map", "0:a:0",
             "-af", f"silencedetect=n={noise}:d={float(max_pause)}", "-f", "null", "-"],
            capture_output=True, text=True).stderr
        starts, found = [], []
        for line in log.splitlines():
            if "silence_start:" in line:
                starts.append(frac(line.split("silence_start:")[1].strip()))
            elif "silence_end:" in line and starts:
                found.append((starts.pop(), frac(line.split("silence_end:")[1].split("|")[0].strip())))
        _silences[key] = found
    return _silences[key]


SNAP_BEFORE = Fraction("0.6")   # how far the in border may move back to reach a silence


def snap_borders(t_in: Fraction, t_out: Fraction, short_gaps) -> tuple[Fraction, Fraction]:
    """Move span borders onto real silences: whisper word times are loose at the edges,
    and a soft first consonant below the threshold gets clipped otherwise."""
    # in border: a silence that covers it, else the nearest silence that ends just before it
    gap = next(((s0, s1) for s0, s1 in short_gaps if s0 <= t_in <= s1), None)
    if gap is None:
        before = [(s0, s1) for s0, s1 in short_gaps if t_in - SNAP_BEFORE < s1 <= t_in]
        gap = max(before, key=lambda g: g[1]) if before else None
    if gap:
        t_in = max(gap[0], gap[1] - PAD_IN)
    # out border: only onto a silence that covers it (or starts a hair after it); never into the next word
    starts = [s0 for s0, s1 in short_gaps if s0 <= t_out + PAD_IN and s1 >= t_out]
    if starts:
        s0 = min(starts)
        s1 = next(b for a, b in short_gaps if a == s0)
        t_out = min(s1, s0 + PAD_OUT)
    return t_in, t_out


def split_span(span: dict, gaps, short_gaps) -> list[tuple[Fraction, Fraction]]:
    """Return (in_s, out_s) pieces of one span after removing the silences inside it."""
    t_in, t_out = snap_borders(frac(span["in_s"]), frac(span["out_s"]), short_gaps)
    if span.get("to_end"):
        return [(t_in, frac(span["out_s"]))]
    pieces, cur_in = [], t_in
    for s0, s1 in gaps:
        cut_from, cut_to = s0 + PAD_OUT, s1 - PAD_IN
        if cut_from > cur_in and cut_to < t_out and cut_to > cut_from:
            pieces.append((cur_in, cut_from))
            cur_in = cut_to
    pieces.append((cur_in, t_out))
    return pieces


def next_version(folder: Path, pattern: str) -> str:
    n = 1
    while any(folder.glob(pattern.format(v=f"v{n:02d}"))):
        n += 1
    return f"v{n:02d}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir")
    ap.add_argument("resolved_plan")
    ap.add_argument("--max-pause", default="0.45", help="seconds; longer silences inside a span are cut")
    ap.add_argument("--noise", default="-35dB", help="silencedetect threshold for pauses")
    ap.add_argument("--edge-noise", default="-30dB", help="silencedetect threshold for span borders")
    args = ap.parse_args()
    vdir = lae.video_dir(args.video_dir)
    plan = json.loads((vdir / args.resolved_plan).read_text(encoding="utf-8"))
    inventory = {c["file"]: c for c in lae.latest_inventory(vdir)["clips"]}
    rates = {inventory[s["clip"]]["rate"] for s in plan["spans"]}
    if len(rates) != 1:
        raise SystemExit(f"error: mixed frame rates {rates}")
    rate = lae.parse_rate(rates.pop())
    max_pause = frac(args.max_pause)
    proxies = vdir / "trabalho" / "proxies"

    # 1. pieces in frames
    pieces, overlays, pos = [], [], 0
    for idx, span in enumerate(plan["spans"]):
        clip_frames = inventory[span["clip"]]["frames"]
        to_end = span.get("to_end") or span["out_frame"] >= clip_frames
        span = {**span, "to_end": to_end}
        span_start = pos
        info = inventory[span["clip"]]
        base = {"span": idx, "clip": span["clip"], "vertical": info["height"] > info["width"]}
        if span.get("broll"):
            pieces.append({**base, "broll": True, "in_frame": span["in_frame"], "out_frame": span["out_frame"]})
            pos += span["out_frame"] - span["in_frame"]
            continue
        proxy = proxies / (Path(span["clip"]).stem + "_proxy.mp4")
        effect = span.get("efeito")
        for t_in, t_out in split_span(span, silences(proxy, max_pause, args.noise), silences(proxy, Fraction("0.12"), args.edge_noise)):
            f_in = max(0, lae.seconds_to_frame(t_in, rate))
            f_out = min(clip_frames, lae.seconds_to_frame(t_out, rate))
            if f_out <= f_in:
                continue
            cuts = [(f_in, f_out, None)]
            if effect and f_out > effect["from_frame"]:
                at = max(f_in, effect["from_frame"])
                cuts = ([(f_in, at, None)] if at > f_in else []) + [(at, f_out, effect["tipo"])]
            for a, b, fx in cuts:
                piece = {**base, "in_frame": a, "out_frame": b}
                if fx:
                    piece["efeito"] = fx
                pieces.append(piece)
                pos += b - a
        for a in span.get("apoio", []):
            length = min(a["frames"], pos - span_start)
            overlays.append({"clip": a["clip"], "at_frame": span_start, "frames": length})

    # 2. filter graph: one input per piece (input seek near the cut, exact trim by frame)
    cmd = [lae.FFMPEG, "-hide_banner", "-loglevel", "error", "-stats"]
    graph, labels = [], []
    for k, p in enumerate(pieces):
        seek = max(0, p["in_frame"] - 30)
        cmd += ["-ss", f"{float(lae.frame_to_seconds(seek, rate)):.6f}", "-i", str(proxies / (Path(p['clip']).stem + "_proxy.mp4"))]
        a, b = p["in_frame"] - seek, p["out_frame"] - seek
        s0 = round(lae.frame_to_seconds(a, rate) * SAMPLE_RATE)
        s1 = round(lae.frame_to_seconds(b, rate) * SAMPLE_RATE)
        dur = float(lae.frame_to_seconds(b - a, rate))
        fx = f",{glitch_pb_filter()}" if p.get("efeito") == "glitch_pb" else ""
        graph.append(f"[{k}:v]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS,{fit_filter(p['vertical'], f'p{k}')}{fx}[v{k}]")
        if p.get("broll"):
            graph.append(f"anullsrc=r={SAMPLE_RATE}:cl=stereo,atrim=end_sample={s1 - s0}[a{k}]")
        else:
            graph.append(f"[{k}:a]aresample={SAMPLE_RATE},atrim=start_sample={s0}:end_sample={s1},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:d={FADE},afade=t=out:st={max(0.0, dur - FADE):.4f}:d={FADE}[a{k}]")
        labels.append(f"[v{k}][a{k}]")
    graph.append(f"{''.join(labels)}concat=n={len(pieces)}:v=1:a=1[vcat][aout]")

    last = "vcat"
    for j, o in enumerate(overlays):
        k = len(pieces) + j
        cmd += ["-i", str(proxies / (Path(o['clip']).stem + "_proxy.mp4"))]
        offset = float(lae.frame_to_seconds(o["at_frame"], rate))
        vertical = inventory[o["clip"]]["height"] > inventory[o["clip"]]["width"]
        graph.append(f"[{k}:v]trim=end_frame={o['frames']},{fit_filter(vertical, f'o{j}')},setpts=PTS-STARTPTS+{offset:.6f}/TB[ov{j}]")
        graph.append(f"[{last}][ov{j}]overlay=eof_action=pass:repeatlast=0[vo{j}]")
        last = f"vo{j}"

    version = next_version(vdir / "final", f"{vdir.name}_rascunho_{{v}}.mp4")
    out = vdir / "final" / f"{vdir.name}_rascunho_{version}.mp4"
    out.parent.mkdir(exist_ok=True)
    tmp = out.with_name(out.stem + ".partial.mp4")  # a failed run never leaves a file under the real name
    tmp.unlink(missing_ok=True)
    cmd += ["-filter_complex", ";".join(graph), "-map", f"[{last}]", "-map", "[aout]",
            "-r", f"{rate.numerator}/{rate.denominator}", "-fps_mode", "cfr",
            "-c:v", "h264_videotoolbox", "-b:v", "10M", "-profile:v", "high",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)]
    subprocess.run(cmd, check=True)
    tmp.rename(out)

    total = sum(p["out_frame"] - p["in_frame"] for p in pieces)
    edl = {"plan": plan["plan"], "rate": f"{rate.numerator}/{rate.denominator}", "max_pause_s": float(max_pause),
           "pieces": pieces, "apoio": overlays, "total_frames": total,
           "total_s": round(float(lae.frame_to_seconds(total, rate)), 3), "output": str(out.relative_to(vdir))}
    lae.write_new(vdir / "trabalho" / f"rascunho_{version}.edl.json", json.dumps(edl, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(pieces)} pieces from {len(plan['spans'])} spans, {total} frames ({edl['total_s']:.1f}s), "
          f"{len(overlays)} apoio, {sum(1 for p in pieces if p.get('broll'))} broll, "
          f"{sum(1 for p in pieces if p.get('vertical'))} vertical, {sum(1 for p in pieces if p.get('efeito'))} efeito")
    print(f"wrote {out.relative_to(lae.ROOT)}")


if __name__ == "__main__":
    main()
