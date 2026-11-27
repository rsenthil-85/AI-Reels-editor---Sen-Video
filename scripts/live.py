"""live.py - the live edit page: watch the edit happen in a browser (Claude's browser pane or any browser).

    python live.py <video or its _edit folder> [--port 8765]        then open http://127.0.0.1:8765

Local only (binds 127.0.0.1), read-only, standard library only. Serves templates/live.html plus, from the edit
folder: live.json (progress from livelog.py), plan.json, words / segments, cut.mp4, the finished video, graphics
thumbnails (one frame pulled from each rendered graphic) and render progress (ffmpeg -progress files).
Only files in the edit folder, the graphics cache, the skill's assets/templates, the source video and the finished
video are served.
"""
import json, os, re, subprocess, sys, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CACHE = os.path.join(os.path.expanduser("~"), ".pro-video-editor", "cache")
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

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query); path = unquote(u.path)
        if path in ("/", "/index.html"): return self.send_file(os.path.join(ROOT, "templates", "live.html"))
        if path == "/api/state":
            st = self.state(); st["progress"] = self.progress(); st["edit_dir"] = ED
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
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"  live edit page: http://127.0.0.1:{port}   (edit folder {ED})", flush=True)
    srv.serve_forever()

if __name__ == "__main__":
    main()
