"""Local timeline editor (CapCut-style) for one video.

    .venv/bin/python scripts/timeline_server.py videos/<date>_<name> [--port 8765]

Opens http://127.0.0.1:8765. The page edits the cut list of the latest finished version
(or the latest saved timeline), previews it from the proxies, saves trabalho/timeline_vNN.json
(never overwrites) and can render it with scripts/finish.py (1080p preview or 4K final).
Only listens on 127.0.0.1. Media is served read-only from trabalho/proxies and assets.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import lae

HERE = Path(__file__).resolve().parent
EDITOR = HERE / "timeline" / "editor.html"
render_state: dict = {"running": False, "log": [], "output": None, "error": None}


def latest(folder: Path, pattern: str) -> Path | None:
    files = sorted(folder.glob(pattern), key=lambda p: [int(n) for n in re.findall(r"_v(\d+)", p.name)] or [0])
    return files[-1] if files else None


def project(vdir: Path) -> dict:
    work = vdir / "trabalho"
    inv = lae.latest_inventory(vdir)
    timeline = latest(work, "timeline_v*.json")
    finished = latest(work, f"{vdir.name}_acabamento_v*.edl.json")
    base = json.loads((timeline or finished).read_text(encoding="utf-8"))
    if timeline is None:
        # first load: start from the approved finish
        draft = json.loads((vdir / base["from_edl"]).read_text(encoding="utf-8"))
        base = {"plan": draft["plan"], "acabamento": base["config"], "rate": base["rate"],
                "pieces": base["pieces"], "apoio": base["apoio"], "source": finished.name}
    # the newest finishing config wins: music and sfx changes apply to every timeline
    config_path = latest(work, "acabamento_v*.json")
    base["acabamento"] = f"trabalho/{config_path.name}"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    plan = json.loads((work / (Path(base["plan"]).stem + ".resolvido.json")).read_text(encoding="utf-8"))
    clips, words = {}, {}
    for c in inv["clips"]:
        proxy = work / "proxies" / (Path(c["file"]).stem + "_proxy.mp4")
        if not proxy.exists():
            continue
        clips[c["file"]] = {"frames": c["frames"], "width": c["width"], "height": c["height"],
                            "duration_s": c["duration_s"], "url": f"/media/proxies/{proxy.name}"}
        t = work / "transcricao" / (Path(c["file"]).stem + ".json")
        if t.exists():
            data = json.loads(t.read_text(encoding="utf-8"))
            words[c["file"]] = [[w["start"], w["end"], w["word"]] for s in data["segments"] for w in s["words"]]
    # show caption corrections in the editor too (same file finish.py uses)
    corr = work / "correcoes_legenda.json"
    for c in json.loads(corr.read_text(encoding="utf-8")) if corr.exists() else []:
        for f, ws in words.items():
            if f"_{c['clip']}_" in f:
                for w in ws:
                    if re.sub(r"[^\w]", "", w[2].lower()) == re.sub(r"[^\w]", "", c["de"].lower()):
                        w[2] = c["para"]
    music = [{**m, "url": "/media/" + m["arquivo"]} for m in config.get("musica", [])]
    return {
        "video": vdir.name, "rate": base["rate"], "loaded_from": (timeline or finished).name,
        "plan": base["plan"], "acabamento": base["acabamento"],
        "pieces": base["pieces"], "apoio": base["apoio"],
        "spans": [s["text"] for s in plan["spans"]],
        "config": {**config, "musica": music}, "clips": clips, "words": words,
        "timelines": sorted(p.name for p in work.glob("timeline_v*.json")),
    }


def validate(body: dict, clips: dict) -> list[dict]:
    pieces = []
    for p in body["pieces"]:
        info = clips[p["clip"]]
        a, b = int(p["in_frame"]), int(p["out_frame"])
        if not 0 <= a < b <= info["frames"]:
            raise ValueError(f"piece out of range: {p['clip']} {a}-{b}")
        pieces.append({"span": p.get("span"), "clip": p["clip"], "vertical": info["height"] > info["width"],
                       "in_frame": a, "out_frame": b, "zoom": float(p.get("zoom", 1.0)),
                       **({"broll": True} if p.get("broll") else {}),
                       **({"som": True} if p.get("broll") and p.get("som") else {}),
                       **({"efeito": "glitch_pb"} if p.get("efeito") else {}),
                       **({"rotulo": str(p["rotulo"])[:80]} if p.get("rotulo") else {}),
                       **({"titulo": str(p["titulo"])[:80]} if p.get("titulo") else {}),
                       **({"nome": str(p["nome"])[:80]} if p.get("nome") else {}),
                       **({"transicao": p["transicao"]} if p.get("transicao") in ("flash", "punch", "fade", "dissolve") else {}),
                       **({"zoom_fim": float(p["zoom_fim"])} if p.get("zoom_fim") else {}),
                       **({"velocidade": float(p["velocidade"])} if p.get("broll") and float(p.get("velocidade") or 1) > 1 else {})})
    return pieces


class Handler(BaseHTTPRequestHandler):
    vdir: Path

    def log_message(self, *args) -> None:  # keep the terminal quiet
        pass

    def send_json(self, data, code=200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            raw = EDITOR.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif path == "/api/project":
            name = urlparse(self.path).query.removeprefix("timeline=")
            data = project(self.vdir)
            if name:
                t = json.loads((self.vdir / "trabalho" / Path(unquote(name)).name).read_text(encoding="utf-8"))
                data.update(pieces=t["pieces"], apoio=t["apoio"], loaded_from=Path(name).name)
            self.send_json(data)
        elif path == "/api/render":
            self.send_json({**render_state, "log": render_state["log"][-6:]})
        elif path.startswith("/media/"):
            self.send_media(path.removeprefix("/media/"))
        else:
            self.send_error(404)

    def send_media(self, rel: str) -> None:
        allowed = [(self.vdir / "trabalho" / "proxies").resolve(), (self.vdir / "assets").resolve(),
                   (self.vdir / "final").resolve()]
        rel = rel.removeprefix("proxies/")
        candidates = [(base / rel).resolve() for base in allowed] + [(self.vdir / rel).resolve()]
        file = next((c for c in candidates if c.is_file() and any(c.is_relative_to(a) for a in allowed)), None)
        if file is None:
            self.send_error(404)
            return
        size = file.stat().st_size
        start, end = 0, size - 1
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if m:
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else end
            else:
                start = size - int(m.group(2))
            end = min(end, size - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with open(file, "rb") as fh:
            fh.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = fh.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if path == "/api/save":
            try:
                proj = project(self.vdir)
                pieces = validate(body, proj["clips"])
            except (KeyError, ValueError) as exc:
                self.send_json({"error": str(exc)}, 400)
                return
            work = self.vdir / "trabalho"
            n = 1
            while (work / f"timeline_v{n:02d}.json").exists():
                n += 1
            name = f"timeline_v{n:02d}.json"
            data = {"plan": proj["plan"], "acabamento": proj["acabamento"], "rate": proj["rate"],
                    "based_on": body.get("based_on"), "zoom_manual": True,
                    "pieces": pieces, "apoio": body.get("apoio", [])}
            lae.write_new(work / name, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            self.send_json({"saved": name})
        elif path == "/api/render":
            if render_state["running"]:
                self.send_json({"error": "já existe um render em andamento"}, 409)
                return
            name = Path(body["timeline"]).name
            source = "bruto" if body.get("source") == "bruto" else "proxies"
            proj = project(self.vdir)
            cmd = [sys.executable, str(HERE / "finish.py"), str(self.vdir), f"trabalho/{name}",
                   f"trabalho/{Path(proj['acabamento']).name}", "--source", source]
            threading.Thread(target=run_render, args=(cmd,), daemon=True).start()
            self.send_json({"started": name, "source": source})
        else:
            self.send_error(404)


def run_render(cmd: list[str]) -> None:
    render_state.update(running=True, log=[], output=None, error=None)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=lae.ROOT)
    buf = ""
    for ch in iter(lambda: proc.stdout.read(1), ""):
        if ch in "\r\n":
            if buf.strip():
                render_state["log"].append(buf.strip())
                render_state["log"] = render_state["log"][-50:]
                if buf.startswith("wrote "):
                    render_state["output"] = buf.removeprefix("wrote ").strip()
            buf = ""
        else:
            buf += ch
    proc.wait()
    if proc.returncode:
        render_state["error"] = f"finish.py saiu com código {proc.returncode}"
    render_state["running"] = False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    Handler.vdir = lae.video_dir(args.video_dir)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"timeline editor: http://127.0.0.1:{args.port}  ({Handler.vdir.name})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
