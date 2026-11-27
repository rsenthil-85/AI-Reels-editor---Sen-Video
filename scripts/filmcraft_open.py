"""filmcraft_open.py - optional: open a finished edit in FilmCraft (free NLE, MIT/Apache-2.0) to adjust it by hand.

    python filmcraft_open.py <video or its _edit folder> [--fc <path to filmcraft.exe>] [--slow 0.3]

Builds the edit on FilmCraft's timeline while the user watches (FilmCraft opens as its own window):
  V1/A1  the original video, placed part by part (the cuts are visible as separate clips)
  V2     a page-colour matte under full cards
  V3     full cards / top panels (our rendered graphics, converted to ProRes 4444 with alpha - FilmCraft can't read qtrle)
  V4     stickers and overlays, positioned like in our edit
  C1     captions (SRT from the cut words, name fixes applied)
  A2     the music bed at the plan's level
Saves <name>_edit/filmcraft/<name>.fcproj. Our renderer (compose.py) still makes the final reel - FilmCraft does not
reproduce our caption styles or the card + face-window layout; it is for hand tweaks, review and its own export.

Finding FilmCraft: --fc, else env FILMCRAFT_EXE, else ~/.pro-video-editor/filmcraft.json {"exe": ...} (written by
install.ps1 -WithFilmCraft), else <skill>/tools/filmcraft/**/filmcraft.exe.
Remote control: FilmCraft's documented JSON control channel on 127.0.0.1 with a fresh random token per launch, kept
only in this process's environment (never printed, never written to disk).
"""
import glob, json, os, re, secrets, socket, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import livelog as LL

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CFG = os.path.join(os.path.expanduser("~"), ".pro-video-editor", "filmcraft.json")
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi")

def find_fc(a):
    if "--fc" in a: return a[a.index("--fc") + 1]
    if os.environ.get("FILMCRAFT_EXE"): return os.environ["FILMCRAFT_EXE"]
    if os.path.exists(CFG):
        try: return json.load(open(CFG, encoding="utf-8-sig"))["exe"]   # PowerShell writes a BOM
        except Exception: pass
    hits = glob.glob(os.path.join(ROOT, "tools", "filmcraft", "**", "filmcraft.exe"), recursive=True)
    return hits[0] if hits else None

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    p = os.path.abspath(a[0])
    ED = p if os.path.isdir(p) else os.path.join(os.path.dirname(p), os.path.splitext(os.path.basename(p))[0] + "_edit")
    name = os.path.basename(ED)[:-5] if ED.endswith("_edit") else os.path.basename(ED)
    src = p if os.path.isfile(p) else next((os.path.join(os.path.dirname(ED), name + e) for e in VIDEO_EXT
                                             if os.path.exists(os.path.join(os.path.dirname(ED), name + e))), None)
    slow = float(a[a.index("--slow") + 1]) if "--slow" in a else 0.3
    fc = find_fc(a)
    if not fc or not os.path.exists(fc):
        print("FilmCraft not found. Install it with:  install.ps1 -WithFilmCraft   (or pass --fc <filmcraft.exe>)"); sys.exit(2)
    cli = os.path.join(os.path.dirname(fc), "filmcraft-cli.exe")
    P = json.load(open(os.path.join(ED, "plan.json"), encoding="utf-8"))
    W, H = (1080, 1920) if P.get("format", "reel") == "reel" else (1920, 1080)
    WC = os.path.join(ED, "work_compose"); out = os.path.join(ED, "filmcraft"); os.makedirs(out, exist_ok=True)
    segs = json.load(open(os.path.join(ED, "segments.json"), encoding="utf-8")) if os.path.exists(os.path.join(ED, "segments.json")) else []
    if not src or not segs:   # no original or no cut list: place the cut video as one clip
        src = os.path.join(ED, P.get("src", "cut.mp4")); segs = None
    t0 = time.time()
    shot_n = [0]
    def shot():   # a picture of FilmCraft's window for the edit page ("what FilmCraft is doing right now")
        shot_n[0] += 1
        try: call("ui.screenshot", path=os.path.join(out, f"screen_{shot_n[0]:02d}.png"))
        except Exception: pass
    for old in glob.glob(os.path.join(out, "screen_*.png")): os.remove(old)
    LL.step(ED, "filmcraft", "doing", "getting the graphics ready for FilmCraft", filmcraft=True)

    # graphics -> ProRes 4444 with alpha (cached next to the originals)
    def prores(m):
        q = m[:-4] + "_fc.mov"
        if not os.path.exists(q) or os.path.getmtime(q) < os.path.getmtime(m):
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", m, "-c:v", "prores_ks", "-profile:v", "4444",
                            "-pix_fmt", "yuva444p10le", "-alpha_bits", "16", q], check=True)
        return q
    gl = [(it, os.path.join(WC, f"ins{i}.mov")) for i, it in enumerate(P.get("inserts", [])) if "gfx" in it and os.path.exists(os.path.join(WC, f"ins{i}.mov"))]
    ol = [(o, os.path.join(WC, f"ov{i}.mov")) for i, o in enumerate(P.get("overlays", [])) if "gfx" in o and os.path.exists(os.path.join(WC, f"ov{i}.mov"))]
    from concurrent.futures import ThreadPoolExecutor   # convert 4 at a time (each ffmpeg is mostly single-threaded)
    with ThreadPoolExecutor(4) as tp: conv = list(tp.map(prores, [m for _, m in gl + ol]))
    gfx = [(it, q) for (it, _), q in zip(gl, conv[:len(gl)])]; ovs = [(o, q) for (o, _), q in zip(ol, conv[len(gl):])]
    music = next(iter(sorted(glob.glob(os.path.join(WC, "music_*.wav")))), None) if P.get("music") else None
    print(f"  graphics ready for FilmCraft ({len(gfx) + len(ovs)}) in {time.time() - t0:.0f} s", flush=True)

    # a fresh project with a sequence the size of our edit, opened straight into FilmCraft (no demo project)
    proj = os.path.join(out, name + ".fcproj")
    steps = [{"id": "file.newProject", "params": {"name": name}},
             {"id": "file.newSequence", "params": {"name": name + " - edit", "width": W, "height": H, "fps": 30, "video": 4, "audio": 3}},
             {"id": "file.saveAs", "params": {"path": proj}}]
    jl = os.path.join(out, "newproject.jsonl"); open(jl, "w", encoding="utf-8").write("\n".join(json.dumps(x) for x in steps) + "\n")
    if os.path.exists(proj): os.remove(proj)
    r = subprocess.run([cli, "run", jl], capture_output=True, text=True)
    if r.returncode != 0: print(r.stdout[-400:], r.stderr[-400:]); sys.exit(1)

    LL.step(ED, "filmcraft", "doing", "opening FilmCraft")
    tok = secrets.token_hex(32); port = free_port()
    env = dict(os.environ, FILMCRAFT_CONTROL_TOKEN=tok)
    subprocess.Popen([fc, proj, "--control", str(port)], env=env, stdout=open(os.path.join(out, "filmcraft.log"), "w"),
                     stderr=subprocess.STDOUT, creationflags=(subprocess.DETACHED_PROCESS if os.name == "nt" else 0))
    for _ in range(120):
        try: s = socket.create_connection(("127.0.0.1", port), timeout=2); break
        except OSError: time.sleep(0.5)
    else: print("FilmCraft did not open its control port (see filmcraft/filmcraft.log)"); sys.exit(1)
    s.settimeout(120); f = s.makefile("rw", encoding="utf-8"); n = [0]

    def call(method, **params):
        n[0] += 1; req = json.dumps({"id": n[0], "token": tok, "method": method, "params": params}) + "\n"
        f.write(req); f.flush(); r = json.loads(f.readline())
        for _ in range(120):   # "still starting" until the first frame is drawn: wait and resend
            if r.get("ok") or "still starting" not in str(r.get("error")): break
            time.sleep(1); f.write(req); f.flush(); r = json.loads(f.readline())
        if not r.get("ok"): print("  ! FilmCraft:", params.get("command", method), "-", r.get("error"), flush=True)
        return r.get("result") or {}
    ex = lambda cmd, **p: call("engine.execute", command=cmd, params=p)

    call("ui.focus")   # started with --control, FilmCraft opens BEHIND other windows on purpose: bring it to the front
    paths = [src] + [q for _, q in gfx] + [q for _, q in ovs] + ([music] if music else [])
    ids = ex("file.import", paths=paths).get("items", [])
    idm = dict(zip(paths, ids))
    # V1/A1: the kept parts one after another - the user sees the cut being made
    t = 0.0
    # phone/WhatsApp footage is often smaller than the frame (576x1024): scale it to cover, like compose.py does
    try:
        st = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                                 "stream=width,height:stream_side_data=rotation:stream_tags=rotate", "-of", "json", src]))["streams"][0]
        sw, sh = st["width"], st["height"]
        rot = int(float(st.get("tags", {}).get("rotate", 0) or next((d.get("rotation", 0) for d in st.get("side_data_list", []) if "rotation" in d), 0)))
        if abs(rot) % 180 == 90: sw, sh = sh, sw   # phones store portrait video sideways + a rotate flag
        cover = round(max(W / sw, H / sh) * 100, 2)
    except Exception: cover = 100
    for sg in (segs or [{"s": 0, "e": None}]):
        prm = dict(item=idm[src], track="V1", audioTrack="A1", seconds=round(t, 3))
        if sg["e"] is not None: prm.update(sourceIn={"seconds": sg["s"]}, duration={"seconds": sg["e"] - sg["s"]})
        r = ex("timeline.place", **prm); t += (sg["e"] - sg["s"]) if sg["e"] is not None else 0
        if cover != 100 and r.get("clips"): ex("effects.setParam", clip=r["clips"][0], effect="motion", param="scale", value=cover)
        time.sleep(slow * 0.4)
    print(f"  cut placed: {len(segs or [1])} parts (scaled {cover:.0f}% to fill the frame)", flush=True)
    LL.step(ED, "filmcraft", "doing", f"cut placed on the timeline ({len(segs or [1])} parts)"); shot()
    # full cards sit on the theme's page colour (our renderer draws them on a canvas): a colour matte under them on V2
    base = P.get("panel_base", "#F4F2EC")
    for it, q in gfx:
        mode = it.get("mode", "top")
        if mode == "card":
            m = ex("file.newColorMatte", color=base, seconds=round(it["t1"] - it["t0"], 3))
            mid = m.get("item") or (m.get("items") or [None])[0]
            if mid: ex("timeline.place", item=mid, track="V2", seconds=it["t0"], audio=False)
        r = ex("timeline.place", item=idm[q], track="V3", seconds=it["t0"], audio=False)
        clip = (r.get("clips") or [None])[0]
        if clip and mode in ("top", "card"):   # these were rendered smaller than the frame: put them where compose puts them
            ch = int(H * 0.72) // 2 * 2; th = int(H * 0.45) // 2 * 2
            y = (H * 0.05 + ch / 2) if mode == "card" else th / 2
            ex("effects.setParam", clip=clip, effect="motion", param="position", value=[W // 2, round(y)])
        time.sleep(slow)
    for o, q in ovs:
        r = ex("timeline.place", item=idm[q], track="V4", seconds=o["t"], audio=False)
        clip = (r.get("clips") or [None])[0]
        if clip and "x" in o:   # stickers sit where our edit puts them (motion position in sequence pixels)
            ex("effects.setParam", clip=clip, effect="motion", param="position", value=[round(o["x"] * W), round(o["y"] * H)])
        time.sleep(slow)
    print(f"  graphics placed: {len(gfx)} cards, {len(ovs)} overlays", flush=True)
    LL.step(ED, "filmcraft", "doing", f"{len(gfx)} cards and {len(ovs)} stickers placed"); shot()
    # captions: 3-word groups from the cut words, name fixes applied
    words = json.load(open(os.path.join(ED, P.get("words", "words_cut.json")), encoding="utf-8")) if P.get("words") else []
    fix = P.get("fix", {})
    def ts(x): return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{x % 60:06.3f}".replace(".", ",")
    cues, g = [], []
    for k, x in enumerate(words):
        g.append(x)
        if len(g) == 3 or x["w"].strip()[-1:] in ".,!?" or k == len(words) - 1:
            txt = " ".join(fix.get(y["w"].strip(".,!?"), y["w"].strip(".,!?")) for y in g)
            cues.append(f"{len(cues) + 1}\n{ts(g[0]['s'])} --> {ts(g[-1]['e'] + 0.1)}\n{txt}\n"); g = []
    if cues:
        srt = os.path.join(out, name + ".srt"); open(srt, "w", encoding="utf-8").write("\n".join(cues))
        cr = ex("captions.import", path=srt, name="Captions")
        if cr.get("track"):
            ex("captions.setStyle", track=cr["track"], font="Poppins", fontStyle="Bold", size=round(H * 0.018), anchor="bottom",
               margin=0.2, outline=4, outlineColor="#000000", color="#FFFFFF")
        print(f"  captions: {cr.get('captions', 0)}", flush=True)
    if music:
        r = ex("timeline.place", item=idm[music], track="A2", seconds=0, duration={"seconds": t or 60}, video=False)
        if r.get("clips"): ex("clip.audioGain", clips=r["clips"], mode="set", db=float(P.get("music_db", -14)))
        print("  music on A2", flush=True)
    call("ui.set", timeline={"fit": True})
    ex("file.save")
    print(f"  -> {proj}  (built in {time.time() - t0:.0f} s; FilmCraft stays open for hand edits)", flush=True)
    time.sleep(1); shot(); call("ui.focus")
    LL.step(ED, "filmcraft", "done", f"open in FilmCraft for your touch-ups (built in {time.time() - t0:.0f} s)", filmcraft_project=proj)

if __name__ == "__main__":
    try: main()
    except (ConnectionError, OSError, json.JSONDecodeError) as e:   # FilmCraft closed or crashed mid-build
        a_ = sys.argv[1:]; p_ = os.path.abspath(a_[0]) if a_ else ""
        ed = p_ if os.path.isdir(p_) else os.path.join(os.path.dirname(p_), os.path.splitext(os.path.basename(p_))[0] + "_edit")
        LL.step(ed, "filmcraft", "done", "FilmCraft closed before it finished - press Open in FilmCraft again")
        print(f"  FilmCraft closed before the edit was finished ({type(e).__name__}); the reel itself is fine. Run again to retry.")
        sys.exit(3)
