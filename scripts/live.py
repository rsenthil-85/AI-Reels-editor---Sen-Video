"""live.py - the edit page: choose the style, watch the edit happen, open it in FilmCraft for touch-ups in a browser (Claude's browser pane or any browser).

    python live.py <video or its _edit folder> [--port 8765] [--open] [--auto]
    python live.py --home [folder] [--port 8765] [--open] [--auto]     (no video yet: the page starts with the upload screen)
    then open http://127.0.0.1:8765

--open: also open it in the normal browser. --home: where raw videos uploaded on the page are saved (default: the
video's folder, else ~/Videos/Pro video editor). --auto: no agent is watching, so the page runs the scripted edit
itself when the user presses Start editing (autoedit.py --answers; no hand-made graphics).

The page has a "New video" button: the user uploads a raw video, live.py saves it, starts autoedit.py --analyze and
switches the page to it. Agents follow the current video through <install>/.state/current.json and wait for the
user's choice with scripts/wait_choice.py. Recent edits (<install>/.state/recent.json, one list per install) can be reopened on the page.

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
ED = None; SRC = None; WORK = None; PORT = 8765; AUTO = False; AN_PROC = None
SETUP = None   # {"state": running|failed, "step": ..., "tail": ...} while the editor installs itself (first run)
VENV = os.path.join(ROOT, ".venv"); VPY = os.path.join(VENV, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV, "bin", "python")
STATE_DIR = os.environ.get("PVE_STATE") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".state")   # per install: a fresh clone starts with no recent edits (set PVE_STATE to share one)
RECENT = os.path.join(STATE_DIR, "recent.json"); THUMBS = os.path.join(STATE_DIR, "thumbs")
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi")
LOCK = threading.Lock()
TYPES = {".html": "text/html; charset=utf-8", ".json": "application/json", ".mp4": "video/mp4", ".png": "image/png",
         ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".ttf": "font/ttf", ".js": "text/javascript"}

def edit_dir_of(p):
    p = os.path.abspath(p)
    if os.path.isdir(p): return p
    return os.path.join(os.path.dirname(p), os.path.splitext(os.path.basename(p))[0] + "_edit")

def recent_list():
    try: r = json.load(open(RECENT, encoding="utf-8"))
    except Exception: r = []
    return [x for x in r if isinstance(x, dict) and os.path.isdir(x.get("edit_dir") or "")]

def set_current(src, ed):
    """Switch the page to another video; agents read <install>/.state/current.json to follow it."""
    global SRC, ED
    with LOCK:
        SRC, ED = src, ed; os.makedirs(ED, exist_ok=True); os.makedirs(STATE_DIR, exist_ok=True)
        r = [x for x in recent_list() if os.path.realpath(x["edit_dir"]) != os.path.realpath(ed)]
        r.insert(0, {"video": src or "", "edit_dir": ed, "t": time.time()})
        json.dump(r[:30], open(RECENT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        json.dump({"video": src, "edit_dir": ed, "port": PORT, "t": time.time()},
                  open(os.path.join(STATE_DIR, "current.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

def start_analysis(src, ed):
    """A video that arrived through the page: analyse it here (transcribe, cut, intake) - no agent needed for this part."""
    global AN_PROC
    if os.path.exists(os.path.join(ed, "intake.json")): return          # analysed before (same file uploaded again)
    LL.reset(ed, video=os.path.basename(src), src=src)
    LL.step(ed, "style", "todo", "waiting for you: pick a style above and press Start editing")
    AN_PROC = subprocess.Popen([sys.executable, os.path.join(HERE, "autoedit.py"), src, "--analyze"],
                               stdout=open(os.path.join(ed, "analyze.log"), "w"), stderr=subprocess.STDOUT)
    proc = AN_PROC
    def watch():
        if proc.wait() != 0 and not os.path.exists(os.path.join(ed, "intake.json")):
            try: last = [x.strip() for x in open(os.path.join(ed, "analyze.log"), encoding="utf-8", errors="replace") if x.strip()][-1][:200]
            except Exception: last = ""
            LL.step(ed, "analyse", "failed", "could not listen to the video. Press + New video and drop it again, or ask your AI assistant to read analyze.log")
            LL.note(ed, "analysis stopped: " + last)
    threading.Thread(target=watch, daemon=True).start()

def run_auto(ch, src, ed):
    """--auto: nobody is watching choice.json, so run the scripted edit (style, length, music, zoom-ins) ourselves."""
    open(os.path.join(ed, "choice.taken"), "w").write("auto")   # at once, so an agent that starts listening now leaves it alone
    def go():
        while not os.path.exists(os.path.join(ed, "intake.json")):   # analysis still running
            if AN_PROC is not None and AN_PROC.poll() is not None and not os.path.exists(os.path.join(ed, "intake.json")):
                LL.note(ed, "analysis failed - see analyze.log"); return
            time.sleep(1)
        ans = {"style": ch["style"] if ch["style"] != "describe" else "mixed",
               "format": {"full": "reel_full", "60": "reel_60", "30": "reel_30"}[ch["length"]],
               "extras": [x for x in ch["extras"] if x in ("music", "zooms", "bg_replace")]}
        if ch.get("captions") not in (None, "", "style"): ans["captions"] = ch["captions"]
        if ch.get("caption_color"): ans["caption_color"] = ch["caption_color"]
        ap = os.path.join(ed, "answers.json"); json.dump(ans, open(ap, "w", encoding="utf-8"), indent=1)
        open(os.path.join(ed, "choice.taken"), "w").write("auto")
        subprocess.Popen([sys.executable, os.path.join(HERE, "autoedit.py"), src, "--answers", ap],
                         stdout=open(os.path.join(ed, "auto_edit.log"), "w"), stderr=subprocess.STDOUT)
    threading.Thread(target=go, daemon=True).start()

def keep_previous(ed):
    """Before editing the same video again: keep the finished video under the old style's name and reset the later steps."""
    try: old = json.load(open(os.path.join(ed, "choice.json"), encoding="utf-8"))
    except Exception: old = {}
    try:
        st = json.load(open(os.path.join(ed, "live.json"), encoding="utf-8"))
        out = st.get("out") or ""
        if out and os.path.exists(out):
            styles = json.load(open(os.path.join(ROOT, "styles", "edit_styles.json"), encoding="utf-8"))
            lbl = "own style" if old.get("style") == "describe" else styles.get(old.get("style"), {}).get("label", old.get("style") or "earlier")
            lbl = re.sub(r"[^A-Za-z0-9 ]+", " ", lbl).strip()
            base, ext = os.path.splitext(out); n, dst = 1, f"{base} ({lbl}){ext}"
            while os.path.exists(dst): n += 1; dst = f"{base} ({lbl} {n}){ext}"
            os.replace(out, dst); LL.note(ed, "previous edit kept as " + os.path.basename(dst))
        for k in ("style", "graphics", "render", "audio", "done", "filmcraft"):
            if k in st.get("steps", {}): st["steps"][k] = {"label": st["steps"][k].get("label", k), "state": "todo", "detail": ""}
        st.pop("out", None); st["start"] = time.time()
        json.dump(st, open(os.path.join(ed, "live.json"), "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as e: LL.note(ed, f"could not reset the last edit: {e}")
    for f in ("choice.taken",):
        try: os.remove(os.path.join(ed, f))
        except OSError: pass

def open_browser(url):
    """Open the page in the normal browser. Windows: the shell's own handler first (works where webbrowser finds
    no browser, e.g. under some agent sandboxes), then webbrowser, then a plain message."""
    try:
        if os.name == "nt": os.startfile(url); return
    except Exception: pass
    try:
        import webbrowser
        if webbrowser.open(url): return
    except Exception: pass
    print(f"  could not open a browser here - open {url} yourself", flush=True)

def setup_watch(proc, log, srv):
    """First run: install.ps1 runs in the background while the page shows its progress; then restart on the editor's own Python."""
    global SETUP
    while proc.poll() is None:
        try:
            lines = [x.rstrip() for x in open(log, encoding="utf-8", errors="replace") if x.strip()]
            steps = [x[4:] for x in lines if x.startswith("==> ")]
            SETUP = {"state": "running", "step": steps[-1] if steps else "starting", "n": len(steps), "tail": lines[-1][:160] if lines else ""}
            mb = os.path.join(ROOT, "assets", "models", "whisper-large-v3-turbo", "model.bin")
            if steps and steps[-1].startswith("Big speech model") and os.path.exists(mb):   # 1.6 GB: say how far it is
                got = os.path.getsize(mb) / 1e6
                SETUP["tail"] = f"downloaded {got:,.0f} of 1,618 MB ({min(got / 1618, 1):.0%})"
        except Exception: pass
        time.sleep(1)
    if proc.returncode == 0 and os.path.exists(VPY):
        SETUP = {"state": "restarting", "step": "ready, opening the editor", "n": 99, "tail": ""}
        threading.Timer(1.5, srv.shutdown).start()   # main() then restarts this page on the editor's own Python
    else:
        try: tail = [x.rstrip() for x in open(log, encoding="utf-8", errors="replace") if x.strip()][-3:]
        except Exception: tail = []
        SETUP = {"state": "failed", "step": "setup stopped", "n": 0, "tail": " | ".join(tail)[:400]}

def go_home():
    global SRC, ED
    SRC = ED = None

def folder_size(p):
    n = 0
    for root, _, files in os.walk(p):
        for f in files:
            try: n += os.path.getsize(os.path.join(root, f))
            except OSError: pass
    return n

def edit_running(ed):
    """True while an edit is still being made (a step is in progress and it is not finished)."""
    try: st = json.load(open(os.path.join(ed, "live.json"), encoding="utf-8")).get("steps", {})
    except Exception: return False
    return (st.get("done", {}) or {}).get("state") != "done" and any((v or {}).get("state") == "doing" for v in st.values())

def recycle(path):
    """Move a folder to the Recycle Bin (it can be restored), never a hard delete."""
    if os.name != "nt": return False
    ps = ("Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("
          "$env:PVE_RECYCLE, 'OnlyErrorDialogs', 'SendToRecycleBin')")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env={**os.environ, "PVE_RECYCLE": path},
                       capture_output=True, timeout=300)
    return r.returncode == 0 and not os.path.exists(path)

def agent_listening():
    """wait_choice.py touches agent.alive every second while it waits for the user's choice."""
    try: return time.time() - float(open(os.path.join(STATE_DIR, "agent.alive")).read()) < 5
    except (OSError, ValueError): return False

def receive(rfile, size, dest):
    left = size
    with open(dest, "wb") as fo:
        while left > 0:
            chunk = rfile.read(min(1 << 20, left))
            if not chunk: break
            fo.write(chunk); left -= len(chunk)
    if left: os.remove(dest)
    return not left

def clean_name(h):
    return re.sub(r"[^\w.\- ]+", "_", os.path.basename(unquote(h or "upload")))[:120].strip() or "upload"

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def allowed(self, p):
        p = os.path.realpath(p); roots = ([os.path.realpath(ED)] if ED else []) + [os.path.realpath(THUMBS), os.path.realpath(CACHE), os.path.realpath(os.path.join(ROOT, "assets")), os.path.realpath(os.path.join(ROOT, "templates"))]
        out = (self.state().get("out") or "")
        return any(p.startswith(r + os.sep) for r in roots) or (out and p == os.path.realpath(out)) or bool(SRC and p == os.path.realpath(SRC))

    def state(self):
        if not ED: return {}
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
        if path == "/api/upload":   # a file from the user's computer (screen recording, screenshots) -> <edit>/materials/
            if not ED: return self.send_json({"ok": False, "error": "upload your video first"})
            name = clean_name(self.headers.get("X-Filename"))
            if os.path.splitext(name)[1].lower() not in (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".png", ".jpg", ".jpeg", ".webp"):
                return self.send_json({"ok": False, "error": "use a video (mp4, mov, webm...) or an image (png, jpg, webp)"})
            size = int(self.headers.get("Content-Length") or 0)
            if size <= 0 or size > 4 * 1024 ** 3: return self.send_json({"ok": False, "error": "file is empty or over 4 GB"})
            md = os.path.join(ED, "materials"); os.makedirs(md, exist_ok=True)
            dest = os.path.join(md, name)
            if not receive(self.rfile, size, dest): return self.send_json({"ok": False, "error": "upload was interrupted"})
            LL.note(ED, f"file received: {name} ({size / 1e6:.1f} MB)")
            return self.send_json({"ok": True, "path": dest, "name": name})
        if path == "/api/new":   # a raw video to edit: save it, analyse it, switch the page to it
            if SETUP: return self.send_json({"ok": False, "error": "The editor is still setting itself up. Drop your video when this page says it is ready."})
            name = clean_name(self.headers.get("X-Filename")); stem, ext = os.path.splitext(name)
            if ext.lower() not in VIDEO_EXT: return self.send_json({"ok": False, "error": "use a video file (mp4, mov, m4v, webm, mkv)"})
            size = int(self.headers.get("Content-Length") or 0)
            if size <= 0 or size > 8 * 1024 ** 3: return self.send_json({"ok": False, "error": "file is empty or over 8 GB"})
            os.makedirs(WORK, exist_ok=True)
            part = os.path.join(WORK, f".upload_{secrets.token_hex(4)}{ext}")
            if not receive(self.rfile, size, part): return self.send_json({"ok": False, "error": "upload was interrupted - try again"})
            dest = os.path.join(WORK, name); n = 2
            while os.path.exists(dest) and os.path.getsize(dest) != size:   # same name, different video: keep both
                dest = os.path.join(WORK, f"{stem} ({n}){ext}"); n += 1
            if os.path.exists(dest): os.remove(part)                         # the same video again: reuse its edit
            else: os.replace(part, dest)
            set_current(dest, edit_dir_of(dest)); start_analysis(dest, ED)
            return self.send_json({"ok": True, "video": dest})
        try: body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 20000)) or b"{}")
        except Exception: return self.send_error(400)
        if path == "/api/open":   # reopen one of the recent edits
            r = recent_list(); i = body.get("i")
            if not isinstance(i, int) or not 0 <= i < len(r): return self.send_json({"ok": False, "error": "not found"})
            src = r[i].get("video") or None; set_current(src if src and os.path.isfile(src) else None, r[i]["edit_dir"])
            if SRC and not os.path.exists(os.path.join(ED, "live.json")): start_analysis(SRC, ED)
            if os.path.exists(os.path.join(ED, "plan.json")) and not os.path.exists(os.path.join(ED, "choice.taken")):
                open(os.path.join(ED, "choice.taken"), "w").write("old")   # an old edit: don't hand its choice to an agent again
            return self.send_json({"ok": True})
        if path == "/api/forget":   # remove an edit from Recent edits; optionally its _edit folder to the Recycle Bin
            r = recent_list(); i = body.get("i")
            if not isinstance(i, int) or not 0 <= i < len(r): return self.send_json({"ok": False, "error": "not found"})
            ed = r[i]["edit_dir"]; files = bool(body.get("files"))
            if files:
                if edit_running(ed): return self.send_json({"ok": False, "error": "This edit is still being made. Wait for it to finish, or remove it from the list only."})
                if not (os.path.basename(os.path.normpath(ed)).endswith("_edit") and os.path.isdir(ed)):
                    return self.send_json({"ok": False, "error": "Only an edit's own _edit folder can be removed."})
            with LOCK:
                keep = [x for x in recent_list() if os.path.realpath(x["edit_dir"]) != os.path.realpath(ed)]
                json.dump(keep, open(RECENT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
                if ED and os.path.realpath(ED) == os.path.realpath(ed):   # the open edit: back to the start screen
                    go_home()
                    json.dump({"video": None, "edit_dir": None, "port": PORT, "t": time.time()},
                              open(os.path.join(STATE_DIR, "current.json"), "w", encoding="utf-8"), indent=1)
            freed = 0
            if files:
                freed = folder_size(ed)
                if not recycle(ed): return self.send_json({"ok": True, "removed": True, "error": "Removed from the list, but the folder could not be moved to the Recycle Bin: " + ed})
            return self.send_json({"ok": True, "removed": True, "freed_mb": round(freed / 1e6)})
        if not ED: return self.send_json({"ok": False, "error": "upload your video first"})
        if path == "/api/choose":   # style / length / extras / finish - Claude (watching choice.json) takes it from here
            if ED and os.path.exists(os.path.join(ED, "choice.json")):   # edit again with other choices
                if edit_running(ED): return self.send_json({"ok": False, "error": "This edit is still running - wait for it to finish"})
                keep_previous(ED)
            styles = json.load(open(os.path.join(ROOT, "styles", "edit_styles.json"), encoding="utf-8"))
            ch = {"style": body.get("style") if body.get("style") in styles or body.get("style") == "describe" else "mixed",
                  "describe": str(body.get("describe", ""))[:600],
                  "length": body.get("length") if body.get("length") in ("full", "60", "30") else "full",
                  "extras": [x for x in body.get("extras", []) if x in ("music", "zooms", "stickers", "checklist", "motion_bg", "bg_replace", "toon")],
                  "captions": body.get("captions") if body.get("captions") in ("karaoke", "pill", "duo", "stack", "minimal", "none") else "style",
                  "caption_color": body.get("caption_color") if re.fullmatch(r"#[0-9A-Fa-f]{6}", str(body.get("caption_color") or "")) else "",
                  "finish": "filmcraft" if body.get("finish") == "filmcraft" else "auto",
                  "materials": str(body.get("materials", ""))[:2000], "t": time.time()}
            json.dump(ch, open(os.path.join(ED, "choice.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            lbl = "your own description" if ch["style"] == "describe" else styles[ch["style"]]["label"]
            LL.step(ED, "style", "doing", f"{lbl} - planning the graphics" + (", then FilmCraft" if ch["finish"] == "filmcraft" else ""))
            LL.note(ED, "choice received: " + lbl)
            if ch["finish"] == "filmcraft": LL.step(ED, "filmcraft", "todo", "after the edit is finished")
            if SRC and (AUTO or not agent_listening()):   # nobody to hand it to: edit it here so the page never waits forever
                if not AUTO: LL.note(ED, "no AI agent is listening, so the automatic edit runs (no hand-made graphics); ask in the chat for the full version")
                LL.step(ED, "style", "doing", f"{lbl} - automatic edit")
                run_auto(ch, SRC, ED)
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
        if path == "/api/whoami":   # start.ps1 asks this to reuse this install's page instead of starting a second one
            return self.send_json({"app": "pro-video-editor", "install": os.path.realpath(ROOT)})
        if path == "/api/state":
            rec = []
            for i, x in enumerate(recent_list()[:12]):
                try: lj = json.load(open(os.path.join(x["edit_dir"], "live.json"), encoding="utf-8"))
                except Exception: lj = {}
                fin = (lj.get("steps", {}).get("done", {}) or {}).get("state") == "done"
                rec.append({"i": i, "name": os.path.basename(x.get("video") or x["edit_dir"]), "t": x.get("t", 0),
                            "status": "finished" if fin else ("editing" if lj.get("style") or os.path.exists(os.path.join(x["edit_dir"], "choice.json")) else "waiting for a style"),
                            "style": lj.get("style") or "", "current": bool(ED) and os.path.realpath(x["edit_dir"]) == os.path.realpath(ED)})
            if not ED:
                return self.send_json({"home": True, "recent": rec, "work_dir": WORK, "setup": SETUP})
            st = self.state(); st["recent"] = rec; st["work_dir"] = WORK;  st["progress"] = self.progress(); st["edit_dir"] = ED
            st["styles"] = {k: {"label": v["label"], "tagline": v.get("tagline", ""), "caption": v.get("caption", "karaoke"), "accent": v.get("accent", "")} for k, v in
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
        if path == "/api/words" and ED:
            out = {}
            for k in ("words.json", "words_cut.json", "segments.json"):
                fp = os.path.join(ED, k)
                if os.path.exists(fp): out[k[:-5]] = json.load(open(fp, encoding="utf-8"))
            return self.send_json(out)
        if path == "/api/size":   # how much space an edit's working folder takes (for the remove box)
            r = recent_list(); i = q.get("i", [""])[0]
            if not i.isdigit() or int(i) >= len(r): return self.send_json({"ok": False})
            ed = r[int(i)]["edit_dir"]
            return self.send_json({"ok": True, "mb": round(folder_size(ed) / 1e6), "folder": ed, "running": edit_running(ed)})
        if path == "/rthumb":   # first look at a recent video for the Recent edits list
            r = recent_list(); i = int((q.get("i", ["-1"])[0]) or -1) if (q.get("i", ["-1"])[0]).lstrip("-").isdigit() else -1
            if not 0 <= i < len(r): return self.send_error(404)
            v = r[i].get("video") or ""; fin = os.path.join(r[i]["edit_dir"], "live.json")
            try: out = json.load(open(fin, encoding="utf-8")).get("out") or ""
            except Exception: out = ""
            v = out if out and os.path.isfile(out) else v
            if not os.path.isfile(v): return self.send_error(404)
            os.makedirs(THUMBS, exist_ok=True)
            t = os.path.join(THUMBS, re.sub(r"[^\w]+", "_", v)[-80:] + f"_{os.path.getmtime(v):.0f}.jpg")
            if not os.path.exists(t):
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", "1.5", "-i", v, "-frames:v", "1", "-vf", "scale=-2:240", "-q:v", "4", t])
            return self.send_file(t)
        if path.startswith("/assets/"): return self.send_file(os.path.join(ROOT, path[1:]))
        if not ED: return self.send_error(404)
        if path == "/thumb": return self.thumb(q.get("f", [""])[0], q.get("t", ["50%"])[0])
        if path == "/file": return self.send_file(q.get("f", [""])[0])
        if path.startswith("/e/"):
            if ".page_token" in path: return self.send_error(404)   # never hand the page code out as a file
            return self.send_file(os.path.join(ED, path[3:]))
        self.send_error(404)

def main():
    global WORK, PORT, AUTO, PAGE_TOKEN
    global SETUP
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    me = [os.path.abspath(__file__)] + a
    if os.path.exists(VPY) and os.path.realpath(sys.prefix) != os.path.realpath(VENV):
        # started with another Python (an assistant ran "python live.py"): the speech and video libraries live in the
        # editor's own environment, so run there
        print("  switching to the editor's own Python", flush=True)
        sys.exit(subprocess.call([VPY, "-u"] + me))
    AUTO = "--auto" in a
    vid = a[0] if not a[0].startswith("--") else None
    hv = a[a.index("--home") + 1] if "--home" in a and a.index("--home") + 1 < len(a) and not a[a.index("--home") + 1].startswith("--") else None
    if vid: ed0 = edit_dir_of(vid); WORK = hv or os.path.dirname(os.path.abspath(ed0))
    else: ed0 = None; WORK = hv or os.path.join(os.path.expanduser("~"), "Videos", "Pro video editor")
    WORK = os.path.abspath(WORK)
    # one page code, kept across restarts: a tab opened before a restart can still press Start
    os.makedirs(STATE_DIR, exist_ok=True)
    tf = os.path.join(ed0, ".page_token") if ed0 else os.path.join(STATE_DIR, ".page_token")
    if ed0: os.makedirs(ed0, exist_ok=True)
    try: PAGE_TOKEN = open(tf).read().strip() or PAGE_TOKEN
    except OSError: open(tf, "w").write(PAGE_TOKEN)
    port = int(a[a.index("--port") + 1]) if "--port" in a else 8765
    class Srv(ThreadingHTTPServer):
        # Python's default (allow_reuse_address) lets a second server share a port on Windows, so an old edit's page kept
        # answering. Exclusive bind: a busy port fails, and the loop below moves to the next one.
        allow_reuse_address = False
        def server_bind(self):
            import socket as _s
            if hasattr(_s, "SO_EXCLUSIVEADDRUSE"): self.socket.setsockopt(_s.SOL_SOCKET, _s.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()
    for _ in range(20):   # an earlier edit's page may still hold the port: take the next free one
        try: srv = Srv(("127.0.0.1", port), H); break
        except OSError: port += 1
    else: print("  no free port for the edit page"); sys.exit(1)
    PORT = port
    if vid: set_current(os.path.abspath(vid) if os.path.isfile(vid) else None, ed0)
    print(f"  live edit page: http://127.0.0.1:{port}   " + (f"(edit folder {ED})" if ED else f"(start screen; uploads saved in {WORK})"), flush=True)
    url = f"http://127.0.0.1:{port}/"
    print(f"  open this link in your browser if it does not open by itself: {url}", flush=True)
    if "--open" in a:   # also open it in the computer's normal browser (other agents, or no browser pane)
        threading.Timer(0.8, open_browser, args=(url,)).start()
    if not os.path.exists(VPY):   # first run: set the editor up by itself while the page shows the progress
        if os.name != "nt":
            print("  first run: run install.ps1 (Windows) to set up the editor; Mac/Linux setup is not automatic yet", flush=True)
        else:
            log = os.path.join(STATE_DIR, "setup.log")
            print("  first run: setting up the editor (5 to 10 minutes, downloads about 2.5 GB). Progress: " + log, flush=True)
            SETUP = {"state": "running", "step": "starting", "n": 0, "tail": ""}
            proc = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(ROOT, "install.ps1"), "-Target", ROOT],
                                    stdout=open(log, "w", encoding="utf-8"), stderr=subprocess.STDOUT, cwd=ROOT)
            threading.Thread(target=setup_watch, args=(proc, log, srv), daemon=True).start()
    srv.serve_forever()
    if SETUP and SETUP.get("state") == "restarting":   # set up: same page, now on the editor's own Python
        srv.server_close()
        me = [x for x in me if x != "--open"]   # the browser tab is already open
        if "--port" in me: me[me.index("--port") + 1] = str(port)
        else: me += ["--port", str(port)]
        sys.exit(subprocess.call([VPY, "-u"] + me))

if __name__ == "__main__":
    main()
