"""Resolve a text cut plan into times and frames.

    python scripts/resolve_plan.py videos/<date>_<name> trabalho/plano_vNN.md

Plan lines (anything else in the file is ignored):

- `- <clip> "<exact transcript text>"`: a spoken span. The text is matched against the clip's
  words (case and punctuation ignored) and must match exactly once.
  `- <clip>@N "..."` takes the N-th match when the same words were said several times.
  `+fim` after the quote keeps the picture (and the pauses) until the clip ends.
- `- apoio <clip>`: that whole clip's picture over the previous span; the sound stays.
- `- efeito glitch_pb desde "<words>"`: from those words (inside the previous span) to the end of
  that span, a glitch hit and then black and white.
- `- broll <clip> <seconds>s`: picture-only shot (no sound) taken from the middle of the clip.

Writes <plan>.resolvido.json next to the plan (never overwrites) and prints each span.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from fractions import Fraction
from pathlib import Path

import lae

LINE = re.compile(r'^\s*-\s*(\d{4})(?:@(\d+))?\s+"(.+)"\s*(\+fim)?\s*$')
INSERT = re.compile(r'^\s*-\s*apoio\s+(\d{4})\b')
EFFECT = re.compile(r'^\s*-\s*efeito\s+(glitch_pb)\s+desde\s+"(.+)"\s*$')
BROLL = re.compile(r'^\s*-\s*broll\s+(\d{4})\s+([\d.,]+)s\b')
PAD_IN = Fraction("0.08")    # seconds before the first word
PAD_OUT = Fraction("0.15")   # seconds after the last word
MIN_WORD = Fraction("0.10")  # duration given to words whisper returned with start == end


def norm(token: str) -> str:
    token = unicodedata.normalize("NFC", token.lower())
    return re.sub(r"[^\w]", "", token)


def load_words(vdir: Path, clip: str) -> tuple[Path, list[dict]]:
    path = next((vdir / "trabalho" / "transcricao").glob(f"*_{clip}_*.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    return path, [w for s in data["segments"] for w in s["words"]]


def find_all(words: list[dict], quote: str, lo: int = 0, hi: int | None = None) -> list[int]:
    target = [t for t in (norm(x) for x in quote.split()) if t]
    tokens = [norm(w["word"]) for w in words]
    hi = len(tokens) if hi is None else hi
    return [i for i in range(lo, hi - len(target) + 1) if tokens[i:i + len(target)] == target], len(target)


def find_span(words: list[dict], quote: str, nth: int | None) -> tuple[int, int]:
    hits, n = find_all(words, quote)
    if nth is not None:
        if not 1 <= nth <= len(hits):
            raise SystemExit(f"error: {quote!r} has {len(hits)} matches, asked for @{nth}")
        return hits[nth - 1], hits[nth - 1] + n - 1
    if len(hits) != 1:
        raise SystemExit(f"error: {len(hits)} matches for {quote!r} (use <clip>@N to pick one)")
    return hits[0], hits[0] + n - 1


def clip_info(clips: dict, clip: str) -> dict:
    return next(c for f, c in clips.items() if f"_{clip}_" in f)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir")
    ap.add_argument("plan")
    args = ap.parse_args()
    vdir = lae.video_dir(args.video_dir)
    plan = (vdir / args.plan).resolve()
    clips = {c["file"]: c for c in lae.latest_inventory(vdir)["clips"]}

    spans = []
    for line in plan.read_text(encoding="utf-8").splitlines():
        if m := INSERT.match(line):
            if not spans:
                raise SystemExit("error: apoio before any span")
            info = clip_info(clips, m.group(1))
            spans[-1].setdefault("apoio", []).append({"clip": info["file"], "frames": info["frames"]})
            continue
        if m := EFFECT.match(line):
            if not spans or spans[-1].get("broll"):
                raise SystemExit("error: efeito must follow a spoken span")
            prev = spans[-1]
            _, words = load_words(vdir, prev["clip"].split("_")[2])
            first, last = prev["word_range"]
            hits, _ = find_all(words, m.group(2), first, last + 1)
            if len(hits) != 1:
                raise SystemExit(f"error: {len(hits)} matches for efeito {m.group(2)!r} inside the previous span")
            rate = lae.parse_rate(prev["rate"])
            at = max(Fraction(str(words[hits[0]]["start"])) - PAD_IN, Fraction(str(prev["in_s"])))
            prev["efeito"] = {"tipo": m.group(1), "from_s": round(float(at), 3),
                              "from_frame": lae.seconds_to_frame(at, rate)}
            continue
        if m := BROLL.match(line):
            info = clip_info(clips, m.group(1))
            rate = lae.parse_rate(info["rate"])
            want = lae.seconds_to_frame(m.group(2).replace(",", "."), rate)
            length = min(want, info["frames"])
            f_in = (info["frames"] - length) // 2
            spans.append({
                "clip": info["file"], "broll": True, "text": "", "to_end": False,
                "in_s": round(float(lae.frame_to_seconds(f_in, rate)), 3),
                "out_s": round(float(lae.frame_to_seconds(f_in + length, rate)), 3),
                "in_frame": f_in, "out_frame": f_in + length, "frames": length, "rate": info["rate"],
                "low_confidence": [],
            })
            continue
        m = LINE.match(line)
        if not m:
            continue
        clip, nth, quote, to_end = m.groups()
        tpath, words = load_words(vdir, clip)
        source = tpath.stem + ".MP4"
        info = clips[source]
        rate = lae.parse_rate(info["rate"])
        first, last = find_span(words, quote, int(nth) if nth else None)

        start = Fraction(str(words[first]["start"]))
        end = max(Fraction(str(words[last]["end"])), Fraction(str(words[last]["start"])) + MIN_WORD)
        clip_end = Fraction(info["duration_s"]).limit_denominator(1000)
        # pad, but never into the neighbouring words
        prev_end = Fraction(str(words[first - 1]["end"])) if first > 0 else Fraction(0)
        next_start = Fraction(str(words[last + 1]["start"])) if last + 1 < len(words) else clip_end
        t_in = max(start - PAD_IN, prev_end, Fraction(0))
        t_out = clip_end if to_end else min(end + PAD_OUT, next_start, clip_end)

        f_in, f_out = lae.seconds_to_frame(t_in, rate), lae.seconds_to_frame(t_out, rate)
        spans.append({
            "clip": source, "text": quote, "word_range": [first, last], "to_end": bool(to_end),
            "in_s": round(float(t_in), 3), "out_s": round(float(t_out), 3),
            "in_frame": f_in, "out_frame": f_out, "frames": f_out - f_in, "rate": info["rate"],
            "low_confidence": [words[i]["word"] for i in range(first, last + 1) if words[i]["probability"] < 0.5],
        })

    total = sum(Fraction(s["frames"]) / lae.parse_rate(s["rate"]) for s in spans)
    out = plan.with_suffix(".resolvido.json")
    lae.write_new(out, json.dumps({"plan": plan.name, "spans": spans, "total_s": round(float(total), 3)},
                                  indent=2, ensure_ascii=False) + "\n")
    for s in spans:
        dur = s["frames"] / float(lae.parse_rate(s["rate"]))
        label = "[b-roll, sem som]" if s.get("broll") else s["text"][:60]
        flag = f"  low: {s['low_confidence']}" if s["low_confidence"] else ""
        print(f"{s['clip'].split('_')[2]} {s['in_s']:7.2f}-{s['out_s']:7.2f} {dur:5.1f}s  {label}{flag}")
        for a in s.get("apoio", []):
            print(f"     apoio {a['clip'].split('_')[2]} ({a['frames']} frames)")
        if "efeito" in s:
            print(f"     efeito {s['efeito']['tipo']} desde {s['efeito']['from_s']:.2f}s")
    print(f"{len(spans)} spans, total {float(total):.1f}s ({float(total) / 60:.2f} min) before pause trimming")
    print(f"wrote {out.relative_to(lae.ROOT)}")


if __name__ == "__main__":
    main()
