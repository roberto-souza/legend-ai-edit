"""Finish an approved rough cut: zoom on jump cuts, captions, music, sound effects, loudness.

    python scripts/finish.py videos/<date>_<name> trabalho/rascunho_vNN.edl.json trabalho/acabamento_vNN.json
    python scripts/finish.py ... --source bruto        # final 4K render from the camera files
    python scripts/finish.py videos/<pasta> trabalho/timeline_vNN.json trabalho/acabamento_vNN.json   # edited timeline

The cuts come from the approved rough-cut EDL; nothing is re-decided here. The finishing config
(written by Claude, approved by the user) says which music and sound effects go where, using
anchors instead of hand-written times:

    {
      "zoom_max": 1.12,                       # punch-in on jump cuts (style ceiling: 1.15)
      "legenda": true,
      "loudnorm_lufs": -14,
      "musica": [{"arquivo": "assets/x.mp3", "sob": "broll", "inicio_faixa_s": 9.6,
                  "volume_db": -3, "fade_in_s": 0.3, "fade_out_s": 1.5}],
      "trilha": {"nivel_lufs": -20, "duck": {"threshold": 0.03, "ratio": 6},
                 "partes": [{"arquivo": "assets/a.mp3", "de": "inicio", "ate": "efeito", "inicio_faixa_s": 0},
                            {"arquivo": "assets/b.mp3", "de": "fim_efeito", "ate": "fim", "fade_out_s": 2}]},
      "sfx": [{"arquivo": "../../sfx/glitch/x.wav", "em": "efeito", "volume_db": 0},
              {"arquivo": "../../sfx/whoosh/x.wav", "em": "trecho:Tardezinha de gravação", "antes_s": 0.25}]
    }

"trilha" is a background bed under the whole video, levelled to nivel_lufs and ducked by the
voice (sidechain), so it rises by itself where nobody talks (b-roll). Leave a gap between parts
where the bed should be silent. SFX are levelled to SFX_LUFS; "volume_db" is an offset from it.

Anchors: "inicio"/"fim" of the video; "broll" the run of b-roll pieces; "efeito" the first frame
of the effect piece and "fim_efeito" the frame after it;
"trecho:<start of the span text>" the first frame of that span. Paths are relative to the
video folder.

Writes final/<name>_acabamento_vNN.mp4 (proxies, 1080p) or final/<name>_vNN.mp4 (bruto, 4K),
plus trabalho/<same stem>.edl.json and the captions .ass. Never overwrites.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from fractions import Fraction
from pathlib import Path

import lae
import motion
from build_draft import GLITCH_FRAMES, SAMPLE_RATE, FADE, glitch_pb_filter, next_version

MAX_WORDS = 4          # words per caption
MAX_CAPTION_S = 1.8
CAPTION_GAP_S = 0.35   # a pause this long starts a new caption
# a caption should not end on a word that leans on the next one
LEANING = {"a", "o", "as", "os", "de", "do", "da", "dos", "das", "e", "que", "um", "uma", "no", "na",
           "em", "pra", "para", "por", "com", "se", "eu", "tu", "você", "ao", "à", "nos", "nas"}


def fit(vertical: bool, w: int, h: int, tag: str, zoom: float, zoom_end: float | None = None, frames: int = 1) -> str:
    """zoom: static punch-in. zoom_end: smooth push from zoom to zoom_end across the piece."""
    if zoom_end is not None and abs(zoom_end - zoom) > 1e-3:
        # scale per frame (eval=frame) then centre-crop: a continuous push, no zoompan jitter
        z = (f",scale=w='trunc({w}*({zoom}+({zoom_end - zoom:.4f})*n/{max(1, frames - 1)})/2)*2':h=-2:eval=frame:flags=bicubic,"
             f"crop={w}:{h},setsar=1")
    else:
        z = f",scale=iw*{zoom}:ih*{zoom},crop={w}:{h},setsar=1" if zoom > 1 else ""
    if not vertical:
        return f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1{z}"
    return (f"split[bg{tag}][fg{tag}];[bg{tag}]scale={w}:-2,crop={w}:{h},boxblur={w // 64}:3,eq=brightness=-0.08[bgb{tag}];"
            f"[fg{tag}]scale=-2:{h}[fgs{tag}];[bgb{tag}][fgs{tag}]overlay=(W-w)/2:0,setsar=1{z}")


def transition_filter(kind: str | None, w: int, h: int) -> str:
    """In-transition on the first frames of a piece (the cut itself stays hard)."""
    if kind == "flash":
        return ",eq=brightness='0.45*max(0,1-n/5)':eval=frame"
    if kind == "punch":
        return (f",scale=w='trunc({w}*(1+0.12*max(0,1-n/6))/2)*2':h=-2:eval=frame:flags=bicubic,"
                f"crop={w}:{h},setsar=1")
    if kind == "fade":
        return ",fade=t=in:st=0:d=0.25"
    return ""


VOICE_LUFS = -16.0     # every spoken piece is levelled to this before the mix
SFX_LUFS = -16.0       # sound effects are levelled to this, then "volume_db" is an offset
MAX_VOICE_GAIN = 12.0


def measure_lufs(path: Path, start_s: float, dur_s: float) -> float | None:
    log = subprocess.run([lae.FFMPEG, "-hide_banner", "-nostats", "-ss", f"{start_s:.3f}", "-t", f"{dur_s:.3f}",
                          "-i", str(path), "-map", "0:a:0", "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
    value = float(m[-1]) if m else None
    return value if value is not None and value > -70 else None


def assign_voice_gain(pieces: list[dict], rate: Fraction, source) -> None:
    """Level each spoken piece to VOICE_LUFS. Pieces under 1.5 s use their clip's median."""
    per_clip: dict[str, list[float]] = {}
    for p in pieces:
        p["voice_gain_db"] = 0.0
        if p.get("broll"):
            continue
        a = float(lae.frame_to_seconds(p["in_frame"], rate))
        d = float(lae.frame_to_seconds(p["out_frame"] - p["in_frame"], rate))
        p["_lufs"] = measure_lufs(source(p["clip"]), a, d) if d >= 1.5 else None
        if p["_lufs"] is not None:
            per_clip.setdefault(p["clip"], []).append(p["_lufs"])
    for p in pieces:
        if p.get("broll"):
            continue
        level = p.pop("_lufs", None)
        if level is None and per_clip.get(p["clip"]):
            vals = sorted(per_clip[p["clip"]])
            level = vals[len(vals) // 2]
        if level is not None:
            p["voice_gain_db"] = round(max(-MAX_VOICE_GAIN, min(MAX_VOICE_GAIN, VOICE_LUFS - level)), 1)


def assign_zoom(pieces: list[dict], zoom_max: float) -> None:
    """Alternate 1.0 / zoom_max inside runs of jump cuts (same horizontal clip, moving forward)."""
    prev = None
    for p in pieces:
        p["zoom"] = 1.0
        jump = (prev is not None and prev["clip"] == p["clip"] and not p.get("broll") and not prev.get("broll")
                and not p.get("vertical") and not p.get("efeito") and p["in_frame"] >= prev["out_frame"])
        if jump:
            p["zoom"] = 1.0 if prev["zoom"] > 1 else zoom_max
        prev = p


def speed(p: dict) -> float:
    """Playback speed of a piece: only b-roll can be sped up (timelapse); speech always plays at 1x."""
    v = float(p.get("velocidade") or 1)
    return v if p.get("broll") and v > 1 else 1.0


def tl_length(p: dict) -> int:
    """Frames a piece occupies on the timeline (after any speed-up)."""
    n = p["out_frame"] - p["in_frame"]
    return n if speed(p) == 1 else max(1, -(-n * 1000 // round(speed(p) * 1000)))


def piece_starts(pieces: list[dict]) -> list[int]:
    pos, out = 0, []
    for p in pieces:
        out.append(pos)
        pos += tl_length(p)
    return out


def resolve_anchor(anchor: str, pieces, starts, spans) -> int:
    if anchor == "inicio":
        return 0
    if anchor == "fim":
        return starts[-1] + tl_length(pieces[-1])
    if anchor == "fim_efeito":
        last = max(i for i, p in enumerate(pieces) if p.get("efeito"))
        return starts[last] + tl_length(pieces[last])
    if anchor == "efeito":
        return next(s for p, s in zip(pieces, starts) if p.get("efeito"))
    if anchor == "broll":
        return next(s for p, s in zip(pieces, starts) if p.get("broll"))
    if anchor.startswith("trecho:"):
        text = anchor.split(":", 1)[1].strip().lower()
        idx = next(i for i, s in enumerate(spans) if s["text"].lower().startswith(text))
        return next(s for p, s in zip(pieces, starts) if p["span"] == idx)
    raise SystemExit(f"error: unknown anchor {anchor!r}")


def norm_word(word: str) -> str:
    return re.sub(r"[^\w]", "", word.lower())


def ass_time(t: float) -> str:
    cs = round(t * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


# spelling kept on screen; each video adds its own names with "nomes_proprios" in the finishing config
CANON = {"whatsapp": "WhatsApp", "lgpd": "LGPD", "brasil": "Brasil", "pix": "Pix", "youtube": "YouTube",
         "instagram": "Instagram", "deus": "Deus"}
PROPER = set(CANON)


def add_proper_names(names: list[str]) -> None:
    for name in names:
        key = re.sub(r"[^\w]", "", name.lower())
        CANON[key] = name
        PROPER.add(key)


def load_corrections(vdir: Path) -> list[dict]:
    """trabalho/correcoes_legenda.json: [{"clip": "0017", "de": "Amei", "para": "olha aí"}].
    The transcript stays as Whisper wrote it; corrections apply on screen only."""
    path = vdir / "trabalho" / "correcoes_legenda.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def apply_corrections(clip: str, words: list, corrections: list[dict]) -> list:
    """words: list of (segment index, word dict). A correction matches a run of whole words."""
    for c in corrections:
        if f"_{c['clip']}_" not in clip:
            continue
        target = [norm_word(t) for t in c["de"].split()]
        out, i = [], 0
        while i < len(words):
            run = [norm_word(w["word"]) for _, w in words[i:i + len(target)]]
            if run == target:
                seg_i, first = words[i]
                last = words[i + len(target) - 1][1]
                tail = re.search(r"[.?!,]*$", last["word"].strip()).group(0)
                out.append((seg_i, {**first, "word": c["para"] + tail, "end": last["end"]}))
                i += len(target)
            else:
                out.append(words[i])
                i += 1
        words = out
    return words


def assign_words(vdir: Path, pieces, rate: Fraction, spans: list[dict]) -> dict[int, list]:
    """Words for each piece, as (segment index, word). Words of a planned take come only from the
    plan's word range ("primeiro vídeo Por" can't happen), and each word goes to exactly one piece:
    the one holding its start, or the next one when it starts just before a cut border."""
    out: dict[int, list] = {}
    cache: dict[str, list] = {}

    def flat(clip: str) -> list:
        if clip not in cache:
            data = json.loads((vdir / "trabalho" / "transcricao" / (Path(clip).stem + ".json")).read_text())
            cache[clip] = [(seg_i, x) for seg_i, seg in enumerate(data["segments"]) for x in seg["words"]]
        return cache[clip]

    by_span: dict[int, list[int]] = {}
    for k, p in enumerate(pieces):
        if p.get("broll"):
            continue
        sp = p.get("span")
        if isinstance(sp, int) and sp < len(spans) and "word_range" in spans[sp] and spans[sp]["clip"] == p["clip"]:
            by_span.setdefault(sp, []).append(k)
        else:  # piece added by hand in the editor: plain time window
            t0, t1 = lae.frame_to_seconds(p["in_frame"], rate), lae.frame_to_seconds(p["out_frame"], rate)
            out[k] = [(si, x) for si, x in flat(p["clip"])
                      if t0 - Fraction("0.25") <= Fraction(str(x["start"])) < t1 - Fraction("0.12")]
    for sp, ks in by_span.items():
        lo, hi = spans[sp]["word_range"]
        windows = [(k, lae.frame_to_seconds(pieces[k]["in_frame"], rate),
                    lae.frame_to_seconds(pieces[k]["out_frame"], rate)) for k in ks]
        for k in ks:
            out.setdefault(k, [])
        for i, (si, x) in enumerate(flat(pieces[ks[0]]["clip"])):
            if not lo <= i <= hi:
                continue
            start, end = Fraction(str(x["start"])), Fraction(str(x["end"]))
            home = next((k for k, t0, t1 in windows if t0 <= start < t1 - Fraction("0.12")), None)
            if home is None:  # started just before a border, still heard after it
                home = next((k for k, t0, t1 in sorted(windows, key=lambda w: w[1])
                             if t0 > start and end > t0 + Fraction("0.08") and t0 - start < Fraction("0.6")), None)
            if home is not None:
                out[home].append((si, x))
    return out


def captions(vdir: Path, pieces, starts, rate: Fraction, w: int, h: int, spans: list[dict],
             highlight: str | None = None, ass_titles: bool = True, ass_names: bool = True) -> str:
    events, labels, titles, names = [], [], [], []
    assigned = assign_words(vdir, pieces, rate, spans)
    corrections = load_corrections(vdir)
    for k, (p, start) in enumerate(zip(pieces, starts)):
        t0 = lae.frame_to_seconds(p["in_frame"], rate)
        t1 = lae.frame_to_seconds(p["out_frame"], rate)
        off = float(lae.frame_to_seconds(start, rate) - t0)
        if p.get("rotulo"):
            a, b = float(lae.frame_to_seconds(start, rate)), float(lae.frame_to_seconds(start + tl_length(p), rate))
            if labels and labels[-1][2] == p["rotulo"] and abs(labels[-1][1] - a) < 0.05:
                labels[-1] = (labels[-1][0], b, p["rotulo"])   # one label across the pieces of a take
            else:
                labels.append((a, b, p["rotulo"]))
        a_p, b_p = float(lae.frame_to_seconds(start, rate)), float(lae.frame_to_seconds(start + tl_length(p), rate))
        if p.get("titulo"):
            titles.append((a_p, min(b_p, a_p + 3.0), p["titulo"]))
        if p.get("nome"):
            names.append((a_p, min(b_p, a_p + 4.0), p["nome"]))
        if p.get("broll"):
            continue
        words = apply_corrections(p["clip"], assigned.get(k, []), corrections)
        # whisper capitalises the first word of every segment, even mid-sentence: lower it back
        fixed = []
        for i, (seg_i, x) in enumerate(words):
            prev = words[i - 1][1]["word"] if i else ""
            new_seg = i > 0 and seg_i != words[i - 1][0] and x["start"] - words[i - 1][1]["end"] < 1.0
            w0 = x["word"].strip()
            if new_seg and not re.search(r"[.?!]$", prev) and w0[:1].isupper() and not (len(norm_word(w0)) > 1 and w0.isupper()) \
                    and norm_word(w0) not in PROPER:
                x = {**x, "word": w0[:1].lower() + w0[1:]}
            key = norm_word(x["word"])
            if key in CANON:  # proper nouns always spelled the same way
                x = {**x, "word": re.sub(r"[\w]+", CANON[key], x["word"].strip(), count=1)}
            fixed.append((seg_i, x))
        words = fixed
        # a take opens with a capital letter
        first_of_take = k == 0 or pieces[k - 1].get("span") != p.get("span") or p.get("span") is None
        if first_of_take and words and words[0][1]["word"].strip()[:1].islower():
            si, x = words[0]
            w0 = x["word"].strip()
            words[0] = (si, {**x, "word": w0[:1].upper() + w0[1:]})
        group = []
        for i, (seg_i, x) in enumerate(words):
            group.append(x)
            nxt_seg, nxt = words[i + 1] if i + 1 < len(words) else (None, None)
            leaning = norm_word(x["word"]) in LEANING and not re.search(r"[.?!,]$", x["word"])
            end_of_group = (nxt is None
                            or re.search(r"[.?!,]$", x["word"])
                            or nxt["start"] - x["end"] > CAPTION_GAP_S
                            or ((len(group) >= MAX_WORDS or nxt["start"] - group[0]["start"] > MAX_CAPTION_S)
                                and not (leaning and len(group) <= MAX_WORDS + 1)))
            if end_of_group:
                a = max(group[0]["start"], float(t0)) + off
                b = min(x["end"], float(t1), nxt["start"] if nxt else float(t1)) + off
                b = max(b, a + 0.3)
                text = " ".join(g["word"] for g in group).strip(" ,")
                timed = [(g["word"].strip(), max(g["start"], float(t0)) + off) for g in group]
                events.append((a, b, text, timed))
                group = []
    # never overlap: each caption ends where the next begins
    events.sort(key=lambda e: e[0])
    for i in range(len(events) - 1):
        a, b, t, tw = events[i]
        events[i] = (a, min(b, events[i + 1][0]), t, tw)
    size = round(h * 0.05)
    big = round(h * 0.075)
    title = round(h * 0.075)
    name = round(h * 0.042)
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV\n"
            f"Style: Vlog,Helvetica Neue,{size},&H00FFFFFF,&H00000000,&H50000000,-1,1,{max(1, round(size / 24))},"
            f"{max(1, round(size / 40))},2,{w // 10},{w // 10},{round(h * 0.08)}\n"
            f"Style: Rotulo,Helvetica Neue,{big},&H0042B9F5,&H00000000,&H50000000,-1,1,{max(2, round(big / 18))},"
            f"{max(1, round(big / 30))},7,{round(w * 0.05)},{round(w * 0.05)},{round(h * 0.07)}\n"
            f"Style: Titulo,Helvetica Neue,{title},&H00FFFFFF,&H00000000,&H64000000,-1,1,{max(2, round(title / 20))},"
            f"{max(1, round(title / 30))},7,{round(w * 0.05)},{round(w * 0.05)},{round(h * 0.11)}\n"
            f"Style: Nome,Helvetica Neue,{name},&H00FFFFFF,&HC8141416,&H00000000,-1,3,{round(name * 0.45)},0,1,"
            f"{round(w * 0.06)},{round(w * 0.06)},{round(h * 0.2)}\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Text\n")
    pop = r"{\fscx130\fscy130\frz-4\t(0,180,\fscx100\fscy100)}"
    body = ""
    hl = None
    if highlight:  # "#RRGGBB" -> ASS &HBBGGRR&
        rr, gg, bb = highlight.lstrip("#")[0:2], highlight.lstrip("#")[2:4], highlight.lstrip("#")[4:6]
        hl = f"&H{bb}{gg}{rr}&"
    for a, b, text, timed in events:
        if b <= a:
            continue
        if not hl or len(timed) < 2:
            body += f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Vlog,{text}\n"
            continue
        # one event per word: the word being spoken is coloured, the rest stays white
        for j, (word, ws) in enumerate(timed):
            ea = a if j == 0 else ws
            eb = timed[j + 1][1] if j + 1 < len(timed) else b
            if eb <= ea:
                continue
            parts = [(f"{{\\c{hl}}}{wd}{{\\c&HFFFFFF&}}" if jj == j else wd) for jj, (wd, _) in enumerate(timed)]
            body += f"Dialogue: 0,{ass_time(ea)},{ass_time(eb)},Vlog,{' '.join(parts).strip(' ,')}\n"
    body += "".join(f"Dialogue: 1,{ass_time(a)},{ass_time(b)},Rotulo,{pop}{t}\n" for a, b, t in labels if b > a)
    for a, b, t in (titles if ass_titles else []):
        anim = r"{\fad(120,200)\fscx70\fscy70\t(0,220,\fscx100\fscy100)}"
        body += f"Dialogue: 2,{ass_time(a)},{ass_time(b)},Titulo,{anim}{t}\n"
    for a, b, t in (names if ass_names else []):
        x, y = round(w * 0.06), round(h * 0.8)
        main, _, sub = t.partition("·")
        txt = main.strip() + (r"{\fs" + str(round(name * 0.7)) + r"\b0}  " + sub.strip() if sub else "")
        anim = rf"{{\an1\move({x - round(w * 0.04)},{y},{x},{y},0,220)\fad(160,220)}}"
        body += f"Dialogue: 2,{ass_time(a)},{ass_time(b)},Nome,{anim}{txt}\n"
    return head + body


def normalize_loudness(src: Path, dst: Path, lufs: float) -> None:
    """Measure the mix, then apply one fixed gain plus a peak limiter at -1 dBTP.
    loudnorm (even with linear=true) falls back to dynamic mode when peaks get in the way,
    and dynamic mode lifts quiet stretches such as music-only b-roll above the voice."""
    log = subprocess.run([lae.FFMPEG, "-hide_banner", "-nostats", "-i", str(src), "-map", "0:a",
                          "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True, check=True).stderr
    m = json.loads(log[log.rindex("{"):log.rindex("}") + 1])
    gain = lufs - float(m["input_i"])
    af = f"volume={gain:.2f}dB,alimiter=limit=0.891:level=false:attack=5:release=50,aresample={SAMPLE_RATE}"
    subprocess.run([lae.FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(src), "-map", "0:v", "-map", "0:a",
                    "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(dst)],
                   check=True)
    print(f"loudness: measured {m['input_i']} LUFS, gain {gain:+.1f} dB, limiter at -1 dBTP")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir")
    ap.add_argument("edl")
    ap.add_argument("config")
    ap.add_argument("--source", choices=["proxies", "bruto"], default="proxies")
    args = ap.parse_args()
    vdir = lae.video_dir(args.video_dir)
    edl = json.loads((vdir / args.edl).read_text(encoding="utf-8"))
    cfg = json.loads((vdir / args.config).read_text(encoding="utf-8"))
    plan = json.loads((vdir / "trabalho" / (Path(edl["plan"]).stem + ".resolvido.json")).read_text(encoding="utf-8"))
    inventory = {c["file"]: c for c in lae.latest_inventory(vdir)["clips"]}
    rate = lae.parse_rate(edl["rate"])
    final = args.source == "bruto"
    w, h = (3840, 2160) if final else (1920, 1080)
    # camera LUT for the final render: "lut" in the finishing config (path from the project root),
    # "nenhum" for footage that is not log; default: the only .cube in luts/ (or none)
    lut_cfg = cfg.get("lut")
    cubes = sorted((lae.ROOT / "luts").glob("*.cube"))
    lut = None if lut_cfg == "nenhum" else (lae.ROOT / lut_cfg if lut_cfg else (cubes[0] if len(cubes) == 1 else None))
    if final and lut_cfg is None and len(cubes) > 1:
        raise SystemExit('error: more than one LUT in luts/: set "lut" in the finishing config')

    def source(clip: str) -> Path:
        if final:
            return vdir / "bruto" / clip
        return vdir / "trabalho" / "proxies" / (Path(clip).stem + "_proxy.mp4")

    add_proper_names(cfg.get("nomes_proprios", []))
    pieces = [dict(p) for p in edl["pieces"]]
    if not edl.get("zoom_manual"):  # a saved timeline carries the zoom chosen in the editor
        assign_zoom(pieces, float(cfg.get("zoom_max", 1.0)))
    push = float(cfg.get("zoom_suave", 0))
    if push:
        # slow push-in on longer talking shots that have no zoom of their own
        for p in pieces:
            long_enough = p["out_frame"] - p["in_frame"] >= 2.5 * float(rate)
            if long_enough and "zoom_fim" not in p and not p.get("broll") and not p.get("efeito") \
                    and not p.get("vertical"):
                p["zoom_fim"] = round(p["zoom"] + push, 3)
    assign_voice_gain(pieces, rate, lambda c: vdir / "trabalho" / "proxies" / (Path(c).stem + "_proxy.mp4"))
    starts = piece_starts(pieces)
    total = starts[-1] + tl_length(pieces[-1])
    total_s = float(lae.frame_to_seconds(total, rate))
    color = f"lut3d=file='{lut}':interp=tetrahedral," if final and lut else ""

    if final:
        stem = f"{vdir.name}_{next_version(vdir / 'final', vdir.name + '_{v}.mp4')}"
    else:
        stem = f"{vdir.name}_acabamento_{next_version(vdir / 'final', vdir.name + '_acabamento_{v}.mp4')}"
    out = vdir / "final" / f"{stem}.mp4"

    cmd = [lae.FFMPEG, "-hide_banner", "-loglevel", "error", "-stats"]
    graph, labels, n_in = [], [], 0
    for k, p in enumerate(pieces):
        seek = max(0, p["in_frame"] - 30)
        hw = ["-hwaccel", "videotoolbox"] if final else []
        cmd += [*hw, "-ss", f"{float(lae.frame_to_seconds(seek, rate)):.6f}", "-i", str(source(p["clip"]))]
        a, b = p["in_frame"] - seek, p["out_frame"] - seek
        s0 = round(lae.frame_to_seconds(a, rate) * SAMPLE_RATE)
        s1 = round(lae.frame_to_seconds(b, rate) * SAMPLE_RATE)
        dur = float(lae.frame_to_seconds(b - a, rate))
        fx = f",{glitch_pb_filter(w // 1920)}" if p.get("efeito") == "glitch_pb" else ""
        rgb = "format=rgb48le," if final else ""
        n_out = tl_length(p)
        # timelapse: speed up and drop frames back to the timeline rate *before* the LUT and scaling,
        # so only the frames that stay get processed
        fast = (f",setpts=(PTS-STARTPTS)/{speed(p)},fps={rate.numerator}/{rate.denominator},trim=end_frame={n_out}"
                if speed(p) > 1 else "")
        graph.append(f"[{k}:v]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS{fast},{rgb}{color}"
                     f"{fit(p['vertical'], w, h, f'p{k}', p['zoom'], p.get('zoom_fim'), n_out)}"
                     f"{transition_filter(p.get('transicao'), w, h)}{fx}[v{k}]")
        if p.get("broll"):
            silent = round(lae.frame_to_seconds(n_out, rate) * SAMPLE_RATE)
            graph.append(f"anullsrc=r={SAMPLE_RATE}:cl=stereo,atrim=end_sample={silent}[a{k}]")
        else:
            graph.append(f"[{k}:a]aresample={SAMPLE_RATE},atrim=start_sample={s0}:end_sample={s1},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:d={FADE},afade=t=out:st={max(0.0, dur - FADE):.4f}:d={FADE},"
                         f"volume={p['voice_gain_db']}dB[a{k}]")
        labels.append(f"[v{k}][a{k}]")
        n_in += 1
    graph.append(f"{''.join(labels)}concat=n={len(pieces)}:v=1:a=1[vcat][voice]")

    last = "vcat"
    for j, o in enumerate(edl.get("apoio", [])):
        cmd += ["-i", str(source(o["clip"]))]
        info = inventory[o["clip"]]
        offset = float(lae.frame_to_seconds(o["at_frame"], rate))
        rgb = "format=rgb48le," if final else ""
        graph.append(f"[{n_in}:v]trim=end_frame={o['frames']},{rgb}{color}"
                     f"{fit(info['height'] > info['width'], w, h, f'o{j}', 1.0)},setpts=PTS-STARTPTS+{offset:.6f}/TB[ov{j}]")
        graph.append(f"[{last}][ov{j}]overlay=eof_action=pass:repeatlast=0[vo{j}]")
        last = f"vo{j}"
        n_in += 1

    # titles and names: HyperFrames overlays (motion/titulo, motion/nome) when installed; plain text otherwise
    use_motion = motion.available("titulo")
    use_motion_name = motion.available("nome")
    placed_motion = []
    for p, st_frame in zip(pieces, starts):
        jobs = []
        if p.get("titulo") and use_motion:
            jobs.append(("titulo", {"titulo": p["titulo"], "selo": cfg.get("titulo_selo", "")}))
        if p.get("nome") and use_motion_name:
            parts = re.split(r"\s*[|·—]\s*|\s+-\s+", p["nome"].strip(), maxsplit=1)
            nome, funcao = parts[0], parts[1] if len(parts) > 1 else ""
            jobs.append(("nome", {"nome": nome.strip(), "funcao": funcao.strip()}))
        for template, variables in jobs:
            mov = motion.render(vdir, template, variables, h)
            cmd += ["-i", str(mov)]
            offset = float(lae.frame_to_seconds(st_frame, rate))
            graph.append(f"[{n_in}:v]setpts=PTS-STARTPTS+{offset:.6f}/TB[mo{n_in}]")
            graph.append(f"[{last}][mo{n_in}]overlay=eof_action=pass:repeatlast=0:format=auto[vm{n_in}]")
            last = f"vm{n_in}"
            placed_motion.append({template: variables, "arquivo": str(mov.relative_to(vdir)), "at_frame": st_frame})
            n_in += 1

    ass_path = vdir / "trabalho" / f"{stem}.ass"
    if cfg.get("legenda"):
        lae.write_new(ass_path, captions(vdir, pieces, starts, rate, w, h, plan["spans"], cfg.get("legenda_destaque"),
                                          ass_titles=not use_motion, ass_names=not use_motion_name))
        esc = str(ass_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        graph.append(f"[{last}]subtitles=filename='{esc}',format=yuv420p[vout]")
    else:
        graph.append(f"[{last}]format=yuv420p[vout]")

    # audio: voice + background track (ducked under the voice) + music + sfx, then loudness
    graph.append("[voice]asplit=2[voicemix][voicekey]")
    mix, placed = ["[voicemix]"], []
    bed = cfg.get("trilha")
    if bed:
        parts = []
        for k_part, part in enumerate(bed["partes"]):
            a = resolve_anchor(part["de"], pieces, starts, plan["spans"])
            b = resolve_anchor(part["ate"], pieces, starts, plan["spans"])
            a_s, b_s = float(lae.frame_to_seconds(a, rate)), float(lae.frame_to_seconds(b, rate))
            length = b_s - a_s
            src = vdir / part["arquivo"]
            gain = bed.get("nivel_lufs", -20) - (measure_lufs(src, 0, 3600) or -14)
            fi, fo = part.get("fade_in_s", 1.0), part.get("fade_out_s", 0.6)
            cmd += ["-ss", str(part.get("inicio_faixa_s", 0)), "-i", str(src)]
            graph.append(f"[{n_in}:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,atrim=duration={length:.3f},"
                         f"afade=t=in:d={fi},afade=t=out:st={max(0, length - fo):.3f}:d={fo},"
                         f"volume={gain:.2f}dB,adelay={round(a_s * 1000)}:all=1,apad[bed{k_part}]")
            parts.append(f"[bed{k_part}]")
            placed.append({"trilha": part["arquivo"], "at_s": round(a_s, 3), "length_s": round(length, 3),
                           "gain_db": round(gain, 1)})
            n_in += 1
        graph.append(f"{''.join(parts)}amix=inputs={len(parts)}:normalize=0:duration=longest[bedsum]")
        d = bed.get("duck", {})
        graph.append(f"[bedsum][voicekey]sidechaincompress=threshold={d.get('threshold', 0.03)}:ratio={d.get('ratio', 6)}:"
                     f"attack={d.get('attack_ms', 20)}:release={d.get('release_ms', 500)}:makeup=1[bedduck]")
        mix.append("[bedduck]")
    else:
        graph.append("[voicekey]anullsink")
    for m in cfg.get("musica", []):
        at = resolve_anchor(m["sob"], pieces, starts, plan["spans"])
        run = 0
        for p, s in zip(pieces, starts):
            if p.get("broll") and s >= at and s == at + run:
                run += tl_length(p)
        length = float(lae.frame_to_seconds(run, rate)) + m.get("fade_out_s", 1.5)
        at_s = float(lae.frame_to_seconds(at, rate))
        cmd += ["-ss", str(m.get("inicio_faixa_s", 0)), "-i", str(vdir / m["arquivo"])]
        fo = m.get("fade_out_s", 1.5)
        graph.append(f"[{n_in}:a]aresample={SAMPLE_RATE},atrim=duration={length:.3f},"
                     f"afade=t=in:d={m.get('fade_in_s', 0.3)},afade=t=out:st={length - fo:.3f}:d={fo},"
                     f"volume={m.get('volume_db', -3)}dB,adelay={round(at_s * 1000)}:all=1[m{n_in}]")
        mix.append(f"[m{n_in}]")
        placed.append({"musica": m["arquivo"], "at_s": round(at_s, 3), "length_s": round(length, 3)})
        n_in += 1
    auto_sfx = cfg.get("sfx_transicao")
    sfx_list = list(cfg.get("sfx", []))
    # automatic sounds: one per new on-screen label (counter) and one per title
    prev_label = None
    for p, st_frame in zip(pieces, starts):
        lbl = p.get("rotulo")
        if lbl and lbl != prev_label and cfg.get("sfx_rotulo"):
            x = cfg["sfx_rotulo"]
            sfx_list.append({"arquivo": x["arquivo"], "em_quadro": st_frame, "antes_s": x.get("antes_s", 0.0),
                             "volume_db": x.get("volume_db", -6)})
        prev_label = lbl
        if p.get("titulo") and cfg.get("sfx_titulo"):
            x = cfg["sfx_titulo"]
            sfx_list.append({"arquivo": x["arquivo"], "em_quadro": st_frame, "antes_s": x.get("antes_s", 0.0),
                             "volume_db": x.get("volume_db", -10)})
    if auto_sfx:
        for p, st_frame in zip(pieces, starts):
            if p.get("transicao"):
                sfx_list.append({"arquivo": auto_sfx["arquivo"], "em_quadro": st_frame,
                                 "antes_s": auto_sfx.get("antes_s", 0.2), "volume_db": auto_sfx.get("volume_db", -4)})
    for x in sfx_list:
        at = x["em_quadro"] if "em_quadro" in x else resolve_anchor(x["em"], pieces, starts, plan["spans"])
        at_s = max(0.0, float(lae.frame_to_seconds(at, rate)) - x.get("antes_s", 0.0))
        src = (vdir / x["arquivo"]).resolve()
        # library files come at very different levels: bring each to SFX_LUFS, then apply the offset
        gain = SFX_LUFS - (measure_lufs(src, 0, 60) or SFX_LUFS) + x.get("volume_db", 0)
        cmd += ["-i", str(src)]
        graph.append(f"[{n_in}:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,volume={gain:.2f}dB,"
                     f"adelay={round(at_s * 1000)}:all=1[s{n_in}]")
        mix.append(f"[s{n_in}]")
        placed.append({"sfx": x["arquivo"], "at_s": round(at_s, 3), "gain_db": round(gain, 1)})
        n_in += 1
    lufs = cfg.get("loudnorm_lufs", -14)
    graph.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,"
                 f"aresample={SAMPLE_RATE},atrim=duration={total_s:.4f}[aout]")

    venc = (["-c:v", "hevc_videotoolbox", "-b:v", "45M", "-tag:v", "hvc1", "-profile:v", "main"] if final
            else ["-c:v", "h264_videotoolbox", "-b:v", "10M", "-profile:v", "high"])
    out.parent.mkdir(exist_ok=True)
    tmp = out.with_name(out.stem + ".partial.mp4")  # a failed run never leaves a file under the real name
    tmp.unlink(missing_ok=True)
    cmd += ["-filter_complex", ";".join(graph), "-map", "[vout]", "-map", "[aout]",
            "-r", f"{rate.numerator}/{rate.denominator}", "-fps_mode", "cfr", *venc,
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(tmp)]
    subprocess.run(cmd, check=True)
    normalize_loudness(tmp, out, lufs)
    tmp.unlink()

    record = {"from_edl": args.edl, "config": args.config, "source": args.source, "size": [w, h],
              "rate": edl["rate"], "pieces": pieces, "apoio": edl.get("apoio", []), "audio": placed,
              "captions": str(ass_path.relative_to(vdir)) if cfg.get("legenda") else None,
              "motion": placed_motion,
              "total_frames": total, "total_s": round(total_s, 3), "output": str(out.relative_to(vdir))}
    lae.write_new(vdir / "trabalho" / f"{stem}.edl.json", json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    zoomed = sum(1 for p in pieces if p["zoom"] > 1)
    print(f"{len(pieces)} pieces, {total} frames ({total_s:.1f}s), {zoomed} zoomed, "
          f"{len(placed)} audio layers, captions={'yes' if cfg.get('legenda') else 'no'}")
    print(f"wrote {out.relative_to(lae.ROOT)}")


if __name__ == "__main__":
    main()
