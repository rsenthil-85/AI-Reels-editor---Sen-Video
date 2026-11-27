"""live.py - the edit page: choose the style, watch the edit happen, open it in FilmCraft for touch-ups in a browser (Claude's browser pane or any browser).

    python live.py <video or its _edit folder> [--port 8765]        then open http://127.0.0.1:8765

Local only (binds 127.0.0.1), read-only, standard library only. Serves templates/live.html plus, from the edit
folder: live.json (progress from livelog.py), plan.json, words / segments, cut.mp4, the finished video, graphics
thumbnails (one frame pulled from each rendered graphic) and render progress (ffmpeg -progress files).
Only files in the edit folder, the graphics cache, the skill's assets/templates, the source video and the finished
video are served.
"""
import json, os, re, secrets, subprocess, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import livelog as LL
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CACHE = os.path.join(os.path.expanduser("~"), ".pro-video-editor", "cache")
PAGE_TOKEN = secrets.token_hex(16)   # the page sends it back on POST; other sites cannot read it
FC_PROC = None
TYPES = {".html": "text/html; charset=utf-8", ".json": "application/json", ".mp4": "video/mp4", ".png": "image/png",
         ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".ttf": "font/ttf", ".js": "text/javascript"}

def edit_dir_of(p):
    p = os.path.abspath(p)
    if os.path.isdir(p): return p
    return os.path.join(os.path.dirname(p), os.path.splitext(os.path.basename(p))[0] + "_edit")

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def allowed(self, p):
        p = os.path.realpath(p); roots = [os.path.realpath(ED), os.path.realpath(CACHE), os.path.realpath(os.path.join(ROOT, "assets")), os.path.realpath(os.path.join(ROOT, "templates"))]
        out = (self.state().get("out") or "")
        return any(p.startswith(r + os.sep) for r in roots) or (out and p == os.path.realpath(out)) or p == os.path.realpath(SRC or "")

    def state(self):
        try: return json.load(open(os.path.join(ED, "live.json"), encoding="utf-8"))
        except Exception: return {}

    def send_json(self, obj):
        b = json.dumps(obj, ensure_ascii=False).encode(); self.send_response(200)
        self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def send_file(self, p):
        if not (os.path.isfile(p) and self.allowed(p)): self.send_error(404); return
        size = os.path.getsize(p); ext = os.path.splitext(p)[1].lower(); rng = self.headers.get("Range")
        start, end = 0, size - 1
        m = re.match(r"bytes=(\d*)-(\d*)", rng or "")
        if m:
            if m.group(1): start = int(m.group(1)); end = int(m.group(2)) if m.group(2) else size - 1
            else: start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
        self.send_response(206 if m else 200)
        self.send_header("Content-Type", TYPES.get(ext, "application/octet-stream")); self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(end - start + 1))
        if m: self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(p, "rb") as f:
            f.seek(start); left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(1 << 16, left))
                    if not chunk: break
                    self.wfile.write(chunk); left -= len(chunk)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError): pass

    def thumb(self, p, t):
        """One small frame from a video (rendered graphic, cut, final) - cached next to the edit."""
        if not (os.path.isfile(p) and self.allowed(p)): self.send_error(404); return
        td = os.path.join(ED, "live_thumbs"); os.makedirs(td, exist_ok=True)
        key = re.sub(r"[^\w]+", "_", os.path.basename(p)) + f"_{os.path.getmtime(p):.0f}_{t}.png"; out = os.path.join(td, key)
        if not os.path.exists(out):
            ss = t
            if t.endswith("%"):
                try:
                    d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).decode())
                except Exception: d = 2
                ss = f"{d * float(t[:-1]) / 100:.2f}"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", ss, "-i", p, "-frames:v", "1", "-vf", "scale=240:-2,format=rgba", out])   # png keeps transparency
        self.send_file(out)

    def progress(self):
        """Render progress 0-1 from the ffmpeg -progress files of the parallel parts."""
        wd = os.path.join(ED, "work_compose"); st = self.state(); total = st.get("render_dur") or 0
        parts = {}
        if os.path.isdir(wd):
            for f in os.listdir(wd):
                if f.startswith("prog_") and f.endswith(".txt"):
                    try:
                        txt = open(os.path.join(wd, f), encoding="utf-8", errors="ignore").read()
                        us = re.findall(r"out_time_us=(\d+)", txt); parts[f[5:-4]] = (int(us[-1]) / 1e6 if us else 0, "progress=end" in txt)
                    except Exception: pass
        vids = {k: v for k, v in parts.items() if k.startswith("s") or k == "all"}
        n = max(1, len(vids)); seg = total / n if total else 0
        frac = sum(1.0 if done else (min(1, t / seg) if seg else 0) for t, done in vids.values()) / n if vids else 0
        return {"video": round(frac, 3), "parts": {k: {"t": round(t, 1), "done": d} for k, (t, d) in parts.items()}}

    def do_POST(self):
        """The page's two actions. Only from the page itself: it carries a per-launch token that other web pages can't read."""
        path = urlparse(self.path).path
        if self.headers.get("X-Page-Token") != PAGE_TOKEN: return self.send_error(403)
        try: body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 20000)) or b"{}")
        except Exception: return self.send_error(400)
        if path == "/api/choose":   # style / length / extras / finish - Claude (watching choice.json) takes it from here
            styles = json.load(open(os.path.join(ROOT, "styles", "edit_styles.json"), encoding="utf-8"))
            ch = {"style": body.get("style") if body.get("style") in styles or body.get("style") == "describe" else "mixed",
                  "describe": str(body.get("describe", ""))[:600],
                  "length": body.get("length") if body.get("length") in ("full", "60", "30") else "full",
                  "extras": [x for x in body.get("extras", []) if x in ("music", "zooms", "stickers", "checklist", "motion_bg", "bg_replace")],
                  "finish": "filmcraft" if body.get("finish") == "filmcraft" else "auto", "t": time.time()}
            json.dump(ch, open(os.path.join(ED, "choice.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            lbl = "your own description" if ch["style"] == "describe" else styles[ch["style"]]["label"]
            LL.step(ED, "style", "doing", f"{lbl} - planning the graphics" + (", then FilmCraft" if ch["finish"] == "filmcraft" else ""))
            LL.note(ED, "choice received: " + lbl)
            if ch["finish"] == "filmcraft": LL.step(ED, "filmcraft", "todo", "after the edit is finished")
            return self.send_json({"ok": True, "choice": ch})
        if path == "/api/filmcraft":   # open the finished edit in FilmCraft (runs filmcraft_open.py; no Claude needed)
            global FC_PROC
            if FC_PROC and FC_PROC.poll() is None: return self.send_json({"ok": True, "running": True})
            if not os.path.exists(os.path.join(ED, "plan.json")): return self.send_json({"ok": False, "error": "edit not ready yet"})
            FC_PROC = subprocess.Popen([sys.executable, os.path.join(HERE, "filmcraft_open.py"), SRC or ED],
                                       stdout=open(os.path.join(ED, "filmcraft_open.log"), "w"), stderr=subprocess.STDOUT)
            return self.send_json({"ok": True, "started": True})
        self.send_error(404)

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query); path = unquote(u.path)
        if path in ("/", "/index.html"):
            b = open(os.path.join(ROOT, "templates", "live.html"), encoding="utf-8").read().replace("__PAGE_TOKEN__", PAGE_TOKEN).encode()
            self.send_response(200); self.send_header("Content-Type", TYPES[".html"]); self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        if path == "/api/state":
            st = self.state(); st["progress"] = self.progress(); st["edit_dir"] = ED
            st["styles"] = {k: {"label": v["label"], "tagline": v.get("tagline", "")} for k, v in
                            json.load(open(os.path.join(ROOT, "styles", "edit_styles.json"), encoding="utf-8")).items()}
            try:
                import filmcraft_open as FCO; fc = FCO.find_fc([]); st["filmcraft_installed"] = bool(fc and os.path.exists(fc))
            except Exception: st["filmcraft_installed"] = False
            st["filmcraft_running"] = bool(FC_PROC and FC_PROC.poll() is None)
            fd = os.path.join(ED, "filmcraft")
            shots = sorted([x for x in os.listdir(fd) if x.startswith("screen_") and x.endswith(".png")]) if os.path.isdir(fd) else []
            st["filmcraft_screen"] = ("filmcraft/" + shots[-1]) if shots else None
            cp = os.path.join(ED, "choice.json")
            if os.path.exists(cp):
                try: st["choice"] = json.load(open(cp, encoding="utf-8"))
                except Exception: pass
            for k in ("plan.json", "intake.json"):
                fp = os.path.join(ED, k)
                if os.path.exists(fp):
                    try: st[k[:-5]] = json.load(open(fp, encoding="utf-8"))
                    except Exception: pass
            for k in ("cut.mp4",): st["has_" + k.replace(".", "_")] = os.path.exists(os.path.join(ED, k))
            return self.send_json(st)
        if path == "/api/words":
            out = {}
            for k in ("words.json", "words_cut.json", "segments.json"):
                fp = os.path.join(ED, k)
                if os.path.exists(fp): out[k[:-5]] = json.load(open(fp, encoding="utf-8"))
            return self.send_json(out)
        if path == "/thumb": return self.thumb(q.get("f", [""])[0], q.get("t", ["50%"])[0])
        if path == "/file": return self.send_file(q.get("f", [""])[0])
        if path.startswith("/e/"): return self.send_file(os.path.join(ED, path[3:]))
        if path.startswith("/assets/"): return self.send_file(os.path.join(ROOT, path[1:]))
        self.send_error(404)

def main():
    global ED, SRC
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    ED = edit_dir_of(a[0]); os.makedirs(ED, exist_ok=True)
    SRC = a[0] if os.path.isfile(a[0]) else None
    port = int(a[a.index("--port") + 1]) if "--port" in a else 8765
    for _ in range(20):   # an earlier edit's page may still hold the port: take the next free one
        try: srv = ThreadingHTTPServer(("127.0.0.1", port), H); break
        except OSError: port += 1
    else: print("  no free port for the edit page"); sys.exit(1)
    print(f"  live edit page: http://127.0.0.1:{port}   (edit folder {ED})", flush=True)
    srv.serve_forever()

if __name__ == "__main__":
    main()
