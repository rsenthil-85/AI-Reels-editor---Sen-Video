"""compose.py - assemble the final edit from a plan.json: layout, punch-ins, B-roll, graphics, captions, SFX, music, loudness.

    python compose.py plan.json [--preview]      (--preview: 540p ultrafast, for checking)

plan.json (times are on the CUT timeline, seconds):
{
  "format": "reel",                    // "reel" 1080x1920 or "long" 1920x1080
  "src": "work/cut.mp4", "words": "work/words_cut.json", "out": "final.mp4",
  "face_x": 0.5, "face_y": 0.40,       // where the face sits in the frame (fractions), for crops
  "punch": "auto",                     // "auto" | [] | [{"t0":3.1,"t1":5.0,"z":1.15}]
  "inserts": [                         // B-roll / graphics replacing or splitting the picture
    {"t0":0, "t1":2.4, "mode":"top", "gfx":{"type":"title","l1":"If I Had To Make","money":"$1,000","l2":"I Wouldn't Build"}},
    {"t0":8, "t1":12, "mode":"top", "src":"broll/claude_prompt.mp4", "ss": 3.0},
    {"t0":20, "t1":24, "mode":"full", "src":"proof.png", "kb": true},
    {"t0":30, "t1":60, "mode":"bubble", "src":"screen.mp4"}           // long-form: screen + face bubble
  ],
  "overlays": [                        // transparent graphics over whatever is on screen
    {"t":40, "dur":3.5, "gfx":{"type":"lower","name":"Shawn","role":"Insurance sales manager"}},
    {"t":70, "dur":2.5, "gfx":{"type":"counter","value":"$104,219","caption":"in 90 days"}, "sfx":"ding"}
  ],
  "fix": {"Sean": "Shawn"},           // name/term corrections applied to captions
  "captions": true, "caption_y": 0.66, "caption_fs": 70, "emph": ["fable"],
  "music": "music/bed.mp3", "music_db": -24,
  "grade": true, "sharpen": 0.3,         // CAS sharpening 0-1 (skip if the source was AI-upscaled)
  "voice_clean": true                     // RNNoise denoise ("sh" default, or "cb"); false = light FFT only
}
Modes: top = split-stack (insert in top 45%, face in bottom 55%; reels), full = full frame,
bubble = full-frame insert with a rounded face cam bottom-left (long-form demos).
"""
import json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import captions as CAP
import livelog as LL

IMG = (".png", ".jpg", ".jpeg", ".webp")

def probe_wh(p):
    """Display size of the first video stream (phones store portrait video sideways + a rotate flag)."""
    st = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                             "stream=width,height:stream_side_data=rotation:stream_tags=rotate", "-of", "json", p]))["streams"][0]
    w, h = st["width"], st["height"]
    rot = int(float(st.get("tags", {}).get("rotate", 0) or next((d.get("rotation", 0) for d in st.get("side_data_list", []) if "rotation" in d), 0)))
    return (h, w) if abs(rot) % 180 == 90 else (w, h)

def probe_dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).decode().strip())

def sentences(words, max_len=3.5):
    """Phrases for punch-ins: break at punctuation or every ~max_len s; each runs to the next phrase's start."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w); nxt = words[i + 1] if i + 1 < len(words) else None
        if re.search(r"[.!?,;:]$", w["w"]) or (w["e"] - cur[0]["s"] > max_len) or not nxt:
            out.append([cur[0]["s"], cur[-1]["e"]]); cur = []
    for i in range(len(out) - 1): out[i][1] = out[i + 1][0]
    return [tuple(x) for x in out]

def key_colour(src):
    """Median colour of the frame border (top band + side strips) over 5 frames = the wall / green screen."""
    import numpy as np
    from PIL import Image
    import io
    d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]).decode())
    px = []
    for t in (0.1, 0.3, 0.5, 0.7, 0.9):
        png = subprocess.check_output(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{d * t:.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=160:-2",
                                       "-f", "image2pipe", "-c:v", "png", "-"])
        a = np.asarray(Image.open(io.BytesIO(png)).convert("RGB")).astype(float); h, w = a.shape[:2]
        px += [a[: int(h * .12)].reshape(-1, 3), a[:, : int(w * .08)].reshape(-1, 3), a[:, -int(w * .08):].reshape(-1, 3)]
    m = np.median(np.concatenate(px), axis=0)
    return "#%02X%02X%02X" % tuple(int(v) for v in m)

def _light(hexc):
    h = hexc.lstrip("#"); r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4)); return 0.299 * r + 0.587 * g + 0.114 * b > 150

def cover(w, h):  # scale to cover then crop centre
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    plan_path = os.path.abspath(a[0]); base = os.path.dirname(plan_path)
    P = json.load(open(plan_path, encoding="utf-8"))
    rp = lambda p: p if os.path.isabs(p) else os.path.join(base, p)
    preview = "--preview" in a
    reel = P.get("format", "reel") == "reel"
    W, H = (1080, 1920) if reel else (1920, 1080)
    src = rp(P["src"]); dur = probe_dur(src)
    words = json.load(open(rp(P["words"]), encoding="utf-8")) if P.get("words") else []
    for w in words:  # "fix": {"Sean": "Shawn"} - correct names/terms Whisper got wrong
        core = re.sub(r"[^\w$]", "", w["w"])
        if core in P.get("fix", {}): w["w"] = w["w"].replace(core, P["fix"][core])
    work = os.path.join(base, "work_compose"); os.makedirs(work, exist_ok=True)
    fx, fy = P.get("face_x", 0.5), P.get("face_y", 0.40)
    TOP_H = int(H * 0.45) // 2 * 2

    inserts = P.get("inserts", []); overlays = P.get("overlays", [])
    # "outro": {"dur": 3, "gfx": {"type": "endcard", ...}} - extra seconds after the last word for an end card:
    # the source gets a frozen tail + silence (cached), the music runs on under it, the card covers the frame
    if P.get("outro"):
        o = P["outro"]; n = float(o.get("dur", 3.0))
        ext = os.path.join(work, f"src_outro_{n:.1f}.mp4")
        if not os.path.exists(ext) or os.path.getmtime(ext) < os.path.getmtime(src):
            subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", src, "-vf", f"tpad=stop_mode=clone:stop_duration={n}",
                            "-af", f"apad=pad_dur={n}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "15", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", ext], check=True)
        src = ext; dur = probe_dur(src)
        inserts.append({"t0": round(dur - n, 3), "t1": round(dur, 3), "mode": "full", "gfx": o["gfx"], "sfx": o.get("sfx", "whoosh")})
    SRC_WH = probe_wh(src)   # display size (rotation-aware) for source-resolution grading
    # ---- render graphics
    jobs = []  # graphics render in parallel (each is its own headless browser)
    CACHE = os.path.join(os.path.expanduser("~"), ".pro-video-editor", "cache"); os.makedirs(CACHE, exist_ok=True)
    def gfx(params, w, h, d, name):
        out = os.path.join(work, name + ".mov")
        if params.get("_tpl") == "motionbg.html":   # same look = same background: render once per PC, reuse forever
            import hashlib
            out = os.path.join(CACHE, "bg_" + hashlib.sha1(json.dumps([params, w, h, round(d, 2)], sort_keys=True).encode()).hexdigest()[:16] + ".mp4")
        if params.get("type") == "toon" and "cast" not in params:   # this video's own cartoon cast (scripts/toon_cast.py)
            cp = os.path.join(base, "toon_cast.json")
            if not os.path.exists(cp):
                subprocess.run([sys.executable, os.path.join(HERE, "toon_cast.py"), base], capture_output=True)
            if os.path.exists(cp): params = dict(params, cast=json.dumps(json.load(open(cp, encoding="utf-8")), separators=(",", ":")))
        cache = out + ".json"; key = json.dumps([params, w, h, round(d, 2)], sort_keys=True)
        if os.path.exists(out) and os.path.exists(cache) and open(cache).read() == key: return out  # unchanged: reuse
        tpl = "title3d.html" if params.get("type") == "title3d" else "toon.html" if params.get("type") == "toon" else "gfx.html"
        if params.get("type") == "toon": params.setdefault("fps", 24)   # the cartoon style moves on twos at a 24 fps base
        jobs.append((["node", os.path.join(HERE, "render_gfx.mjs"), out, json.dumps(params), "--w", str(w), "--h", str(h),
                      "--dur", f"{d:.2f}", "--template", tpl] + (["--fps", str(params["fps"])] if params.get("fps") else []), cache, key))
        return out
    for i, it in enumerate(inserts):
        if "gfx" in it:
            CH = int(H * 0.72) // 2 * 2
            w, h = (W, TOP_H) if it.get("mode", "top") == "top" else (W, CH) if it.get("mode") == "card" else (W, H)
            params = dict(it["gfx"])
            if P.get("theme"): params.setdefault("theme", P["theme"])           # colour theme for every graphic
            if reel and it.get("mode", "top") in ("top", "card"): params.setdefault("k", 1.35)  # phone-sized graphics
            if params.get("type") == "device":
                params.setdefault("fps", 15)   # slow push-in: 15 fps looks the same and renders twice as fast
                if it.get("mode") == "full": params.setdefault("cy", 0.38); params.setdefault("maxh", 0.64)   # leave the lower part for captions
                elif it.get("mode", "top") == "top": params.setdefault("cy", 0.40); params.setdefault("maxh", 0.62)  # clear of the hook band
                if any(o.get("gfx", {}).get("type") == "bignum" and it["t0"] - 0.2 <= o["t"] <= it["t1"] for o in overlays):
                    params.setdefault("dx", 0.11)                                   # make room for the big number on the left
            it["_src"] = gfx(params, w, h, it["t1"] - it["t0"], f"ins{i}")
        else: it["_src"] = rp(it["src"])
    # transitions: an accent swipe over the top panel each time its content changes (reels, split-stack)
    if P.get("transitions", True) and reel:
        for it in [x for x in inserts if x.get("mode", "top") == "top"]:
            overlays.append({"t": max(0, it["t0"] - 0.18), "dur": 0.45, "gfx": {"type": "wipe"}, "_wipe": True, "sfx": None,
                             "x": 0.5, "y": TOP_H / 2 / H, "_w": W, "_h": TOP_H})
    for i, ov in enumerate(overlays):
        if "pfx" in ov:            # pixelfx effect (vendor/pixelfx, MIT) -> alpha .mov, crisp pixel scaling
            import pixelfx as PFXM
            out_m = os.path.join(work, f"pfx_{ov['pfx'].replace('/', '_')}_{int(ov.get('w', 600))}.mov")
            if not os.path.exists(out_m): PFXM.export(ov["pfx"], out_m, int(ov.get("w", 600)))
            ov["_src"] = out_m; ov.setdefault("dur", 3.0); ov.setdefault("sfx", None)
        elif "src" in ov: ov["_src"] = rp(ov["src"])
        elif ov.get("_wipe"): ov["_src"] = gfx(ov["gfx"], ov["_w"], ov["_h"], ov["dur"], "wipe")  # one file, reused
        else:
            ow, oh = W, H
            if ov["gfx"].get("type") == "sticker":   # small tile, positioned (default: centred low, over the face)
                ow, oh = int(W * (0.5 if ov["gfx"].get("label") else 0.26)) // 2 * 2, int(W * (0.34 if ov["gfx"].get("label") else 0.27)) // 2 * 2
                ov.setdefault("x", 0.5); ov.setdefault("y", 0.80)
            ov["_src"] = gfx(dict(ov["gfx"], **({"theme": P["theme"]} if P.get("theme") and "theme" not in ov["gfx"] else {})), ow, oh, ov["dur"], f"ov{i}")
    # animated panel background behind split-stack graphics: "panel_bg": "auto:aurora|grid|bokeh" or a video path
    panel_bg = P.get("panel_bg")
    if panel_bg and reel:
        if panel_bg.startswith("auto"):
            style = panel_bg.split(":", 1)[1] if ":" in panel_bg else "aurora"
            panel_bg = gfx({"style": style, "acc": P.get("accent", "#E8603C"), "base": P.get("panel_base", "#0d0e14"), "type": "motionbg", "_tpl": "motionbg.html"},
                           W, TOP_H, 8.0, f"panelbg_{style}")
        else: panel_bg = rp(panel_bg)
    # real-background swap (green screen / plain wall, chroma key - no AI model):
    # "bg_replace": {"bg": "auto:paper|dots|grid|aurora|bokeh" or a video/image path, "key": "auto"|"#00FF00",
    #                "similarity": 0.12, "blend": 0.08}
    br = P.get("bg_replace"); bg_full = None
    if br:
        bsrc = br.get("bg", "auto:" + P.get("bg_style", "paper"))
        if bsrc.startswith("auto"):
            st = bsrc.split(":", 1)[1] if ":" in bsrc else "paper"
            bg_full = gfx({"style": st, "acc": br.get("acc", P.get("accent", "#E8603C")), "base": br.get("base", P.get("panel_base", "#16233F")),
                           "type": "motionbg", "_tpl": "motionbg.html"}, W, H, 8.0, f"fullbg_{st}")
        else: bg_full = rp(bsrc)
        if br.get("key", "auto") == "auto": br["key"] = key_colour(src)
        print(f"  background swap: key {br['key']}, similarity {br.get('similarity', 0.12)}")
    cards = [it for it in inserts if it.get("mode") == "card"]
    inset = reel and P.get("split_style") == "inset"
    canvas_bg = None
    if reel and (cards or inset):
        cst = (P.get("panel_bg") or "auto:paper").split(":", 1)[-1] if (P.get("panel_bg") or "").startswith("auto") else "paper"
        canvas_bg = gfx({"style": cst, "acc": P.get("accent", "#E8603C"), "base": P.get("panel_base", "#F4F2EC"),
                         "type": "motionbg", "_tpl": "motionbg.html"}, W, H, 8.0, f"canvas_{cst}")
    seen = set(); jobs[:] = [j for j in jobs if not (j[0][2] in seen or seen.add(j[0][2]))]  # same file rendered once
    for j in jobs:
        if '"_tpl": "motionbg.html"' in j[0][3]: j[0][-1] = "motionbg.html"
    if jobs:   # all graphics in ONE browser (render_gfx --batch); still frames are reused, not re-captured
        import time as _t; t0 = _t.time()
        batch = [{"out": j[0][2], "params": json.loads(j[0][3]), "w": int(j[0][5]), "h": int(j[0][7]), "dur": float(j[0][9]),
                  "template": j[0][11], "opaque": j[0][11] in ("motionbg.html", "toon.html") or json.loads(j[0][3]).get("type") in ("device", "endcard"),
                  "fps": int(json.loads(j[0][3]).get("fps", 30))} for j in jobs]
        bj = os.path.join(work, "gfx_jobs.json"); json.dump(batch, open(bj, "w"))
        LL.step(base, "graphics", "doing", f"0 of {len(jobs)} graphics", gfx_total=len(jobs))
        pr = subprocess.Popen(["node", os.path.join(HERE, "render_gfx.mjs"), "--batch", bj, "--workers", "3"], stdout=subprocess.PIPE, text=True)
        ndone = 0
        for line in pr.stdout:   # one line per finished graphic -> live page shows it straight away
            if line.strip():
                ndone += 1; LL.step(base, "graphics", "doing", f"{ndone} of {len(jobs)} graphics")
                LL.note(base, "graphic ready", last_gfx=line.strip())
        if pr.wait() != 0: raise subprocess.CalledProcessError(pr.returncode, "render_gfx")
        for j in jobs: open(j[1], "w").write(j[2])
        print(f"  rendered {len(jobs)} graphics in {_t.time() - t0:.0f}s")

    # ---- punch-ins
    top_win = [(it["t0"], it["t1"]) for it in inserts if it.get("mode", "top") == "top" and reel]
    busy = [(it["t0"], it["t1"]) for it in inserts]
    punch = P.get("punch", "auto")
    if punch == "auto":
        punch, k = [], 0
        for s, e in sentences(words):
            if any(s < b and e > a0 for a0, b in busy): continue
            k += 1
            if k % 2 == 0 and e - s > 0.8: punch.append({"t0": s, "t1": e, "z": 1.14 if reel else 1.12})
    Z = punch[0]["z"] if punch else 1.0
    en = lambda wins: "+".join(f"between(t,{x:.3f},{y:.3f})" for x, y in wins) or "0"

    shutil.copytree(os.path.join(ROOT, "assets", "fonts"), os.path.join(work, "fonts"), dirs_exist_ok=True)
    def render(mode="all", S=0.0, E=None, out_path=None, tag="all", threads=0, nframes=0):
        """mode all = one pass; video = frames [S,E) only (absolute timeline kept via setpts); audio = full mix only."""
        live = lambda a0, b0: E is None or (b0 > S and a0 < E)
        f = []
        # ---- inputs
        args = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-nostats"] + (["-ss", f"{S:.3f}"] if mode == "video" and S > 0 else []) + ["-i", src]
        n_in = 1
        def add_input(path, t0=None, d=None, ss=None):
            nonlocal n_in
            if path.lower().endswith(IMG): args.extend(["-loop", "1", "-t", f"{d + 0.5:.2f}", "-i", path])
            else:
                if ss: args.extend(["-ss", str(ss)])
                args.extend(["-i", path])
            n_in += 1; return n_in - 1


        if mode != "audio":
            # grade: contrast + warmth, pull green out of indoor walls, gentle vignette; "sharpen": CAS amount for soft footage
            grade = (",eq=contrast=1.08:saturation=1.06:gamma=0.97,colorbalance=rs=0.04:gs=-0.02:bs=-0.03:rm=0.02:gm=-0.03,"
                     "vignette=angle=0.45" if P.get("grade", True) else "")
            if P.get("grade") == "warm":   # studio look (ref 7): warm cinematic - rich contrast, amber mids, teal-free shadows, deeper vignette
                grade = (",eq=contrast=1.14:saturation=1.10:gamma=0.95,colorbalance=rs=0.06:gs=0.0:bs=-0.06:rm=0.05:gm=0.0:bm=-0.05:rh=0.03:bh=-0.03,"
                         "curves=master='0/0.02 0.25/0.22 0.75/0.79 1/0.98',vignette=angle=0.55")
            gcol = grade; gcas = f",cas={P['sharpen']}" if P.get("sharpen") else ""
            if P.get("sharpen"): grade += f",cas={P['sharpen']}"
            f = [f"[0:v]setpts=PTS-STARTPTS+{S:.3f}/TB,fps=30,{cover(W, H) if not reel else ''}".rstrip(",")]
            if reel:  # vertical: cover with face-aware crop
                f[0] = (f"[0:v]setpts=PTS-STARTPTS+{S:.3f}/TB,fps=30,scale={W}:{H}:force_original_aspect_ratio=increase,"
                        f"crop={W}:{H}:'(iw-{W})*{fx}':'(ih-{H})*{max(0, min(1, fy - 0.1))}'")
            if br:
                kb = n_in; args.extend(["-stream_loop", "-1", "-ss", f"{S % 8.0:.3f}", "-i", bg_full] if not bg_full.lower().endswith(IMG) else ["-loop", "1", "-i", bg_full]); n_in += 1
                kc = br["key"].lstrip("#"); r_, g_, b_ = int(kc[0:2], 16), int(kc[2:4], 16), int(kc[4:6], 16)
                spill = ",despill=type=green" if g_ > r_ + 30 and g_ > b_ + 30 else (",despill=type=blue" if b_ > r_ + 30 and b_ > g_ + 30 else "")
                screen = bool(spill) and br.get("method") != "colorkey"   # saturated screen -> chroma (UV) key; plain wall or a
                # flat digital screen ("method": "colorkey") -> RGB colour key incl. brightness (chromakey left people see-through)
                keyf = (f"chromakey=0x{kc}:{br.get('similarity', 0.12)}:{br.get('blend', 0.08)}{spill}" if screen
                        else f"colorkey=0x{kc}:{br.get('similarity', 0.14)}:{br.get('blend', 0.08)}")
                md = br.get("matte")
                if md:   # matte-assisted key: alpha = max(colour key, core) * outer  (core = always person, outer = person can be here)
                    md = rp(md); mv = os.path.exists(os.path.join(md, "core.mp4"))   # moving matte (per second) or still matte
                    sk = ["-ss", f"{S:.3f}"] if (mv and S > 0) else []
                    kcore = n_in; args.extend(sk + ["-i", os.path.join(md, "core.mp4")] if mv else ["-loop", "1", "-i", os.path.join(md, "core.png")]); n_in += 1
                    kout = n_in; args.extend(sk + ["-i", os.path.join(md, "outer.mp4")] if mv else ["-loop", "1", "-i", os.path.join(md, "outer.png")]); n_in += 1
                    msh = f"setpts=PTS-STARTPTS+{S:.3f}/TB," if mv else ""
                    f[0] += f",split=2[kin1][kin2]"
                    f.append(f"[kin1]format=rgba,{keyf},format=rgba,alphaextract,format=gray[ka];"
                             f"[{kcore}:v]{msh}format=gray,scale={W}:{H}[kc];[{kout}:v]{msh}format=gray,scale={W}:{H}[ko];"
                             f"[ka][kc]blend=all_mode=lighten:eof_action=repeat[a1];[a1][ko]blend=all_mode=multiply:eof_action=repeat[am];"
                             f"[kin2]format=yuv420p[kv];[kv][am]alphamerge[fgk]")
                else:
                    if br.get("method") == "colorkey" and (g_ > r_ + 30 or b_ > r_ + 30):
                        # flat digital screen: tight key, then kill the green/blue fringe on hair and shoulders -
                        # despill the edge colour and pull the matte in ~2 px with a 1 px soften (tested: fringe gone)
                        dt = "green" if g_ >= b_ else "blue"
                        f[0] += f",format=rgba,{keyf},despill=type={dt}:mix=0.6:expand=0.3,split=2[kc1][kc2]"
                        f.append("[kc2]alphaextract,erosion,erosion,boxblur=1:1[kal];[kc1][kal]alphamerge[fgk]")
                    else:
                        f[0] += f",format=yuva420p,{keyf}[fgk]"
                f.append(f"[{kb}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},trim=0:{(E if E is not None else dur) - S:.3f},setpts=PTS-STARTPTS+{S:.3f}/TB,"
                         f"format=yuv420p[kbg];[kbg][fgk]overlay=0:0:shortest=0{grade},format=yuv420p,split=4[b0][bz][bs][bb]")
            if br:
                # punch-in stream (background-swap path keeps the full-size method)
                f.append(f"[bz]scale={int(W * Z)//2*2}:{int(H * Z)//2*2},crop={W}:{H}:(iw-{W})/2:'(ih-{H})*{fy}'[z]")
                f.append(f"[b0][z]overlay=0:0:enable='{en([(p['t0'], p['t1']) for p in punch])}'[v0]")
            else:
                # SPEED (same picture): crop to the frame shape and colour-grade at the SOURCE resolution, then scale up once.
                # Phone/WhatsApp footage is ~576x1024, so the grade touches 3.5x fewer pixels (measured 54.6 s -> 20.5 s per part).
                # Zoom-ins are the same crop shrinking at the punch times (sendcmd) instead of a second full-size zoomed copy
                # of every frame. Footage bigger than the frame is scaled down first, then graded.
                sw_, sh_ = SRC_WH
                CW = int(min(sw_, sh_ * W / H)) // 2 * 2; CH = int(min(sh_, sw_ * H / W)) // 2 * 2
                fxc, fyc = (fx, max(0, min(1, fy - 0.1))) if reel else (0.5, 0.5)
                CX = int((sw_ - CW) * fxc) // 2 * 2; CY = int((sh_ - CH) * fyc) // 2 * 2
                small = CW * CH <= W * H
                pre, post = (gcol, gcas) if small else ("", gcol + gcas)
                wins = [p for p in punch if live(p["t0"], p["t1"])]
                zcrop = ""
                if wins:
                    ZW, ZH = int(CW / Z) // 2 * 2, int(CH / Z) // 2 * 2; ZX = (CW - ZW) // 2 // 2 * 2; ZY = int((CH - ZH) * fy) // 2 * 2
                    on = f"[enter] crop@z w {ZW}, [enter] crop@z h {ZH}, [enter] crop@z x {ZX}, [enter] crop@z y {ZY}"
                    off = f"[leave] crop@z w {CW}, [leave] crop@z h {CH}, [leave] crop@z x 0, [leave] crop@z y 0"
                    open(os.path.join(work, f"zoom_{tag}.cmd"), "w").write("".join(f"{p['t0']:.3f}-{p['t1']:.3f} {on}, {off};\n" for p in wins))
                    zcrop = f"sendcmd=f=zoom_{tag}.cmd,crop@z=w={CW}:h={CH}:x=0:y=0,"
                f[0] = f"[0:v]setpts=PTS-STARTPTS+{S:.3f}/TB,fps=30,crop={CW}:{CH}:{CX}:{CY}{pre},split=3[g0][gs][gb]"
                f.append(f"[g0]{zcrop}scale={W}:{H}{post},format=yuv420p[v0]")
                if reel and top_win:   # face for the split / inset window: cut from the source too (the crop below becomes a no-op)
                    FHs = int(CH * (H - TOP_H) / H) // 2 * 2; ys = int(max(0, min(CH - FHs, CH * fy - FHs * 0.45))) // 2 * 2
                    f.append(f"[gs]crop={CW}:{FHs}:0:{ys},scale={W}:{H - TOP_H}{post},format=yuv420p[bs]")
                else: f.append("[gs]null[bs]")
                if any(it.get("mode") == "bubble" for it in inserts): f.append(f"[gb]scale={W}:{H}{post},format=yuv420p[bb]")
                else: f.append("[gb]null[bb]")
            cur = "v0"
            # split-stack base: face crop in bottom, dark top
            if reel and top_win:
                FH = H - TOP_H
                if inset:
                    fw = int(W * 0.86) // 2 * 2; fh = int(FH * 0.86) // 2 * 2
                    mask = os.path.join(work, "inset_mask.png")
                    if not os.path.exists(mask):
                        from PIL import Image, ImageDraw
                        im = Image.new("L", (fw, fh), 0); ImageDraw.Draw(im).rounded_rectangle([0, 0, fw - 1, fh - 1], radius=int(W * 0.05), fill=255); im.save(mask)
                    kc = n_in; args.extend(["-stream_loop", "-1", "-ss", f"{S % 8.0:.3f}", "-i", canvas_bg]); n_in += 1
                    km = n_in; args.extend(["-loop", "1", "-i", mask]); n_in += 1
                    f.append(f"[{kc}:v]scale={W}:{H},trim=0:{(E if E is not None else dur) - S:.3f},setpts=PTS-STARTPTS+{S:.3f}/TB,format=yuv420p[cvs];"
                             f"[bs]crop={W}:{FH}:0:'max(0,min(ih-{FH},ih*{fy}-{FH}*0.45))',scale={fw}:{fh}[fwin];[{km}:v]format=gray,scale={fw}:{fh}[fwm];"
                             f"[fwin][fwm]alphamerge[fwa];[cvs][fwa]overlay=(W-w)/2:{TOP_H + (FH - fh) // 2 + int(H * 0.01)}:shortest=0[sbq]")
                else:
                    f.append(f"[bs]crop={W}:{FH}:0:'max(0,min(ih-{FH},ih*{fy}-{FH}*0.45))',pad={W}:{H}:0:{TOP_H}:color=0x{P.get('panel_base', '#121214').lstrip('#')}[sbp]")
                if inset: pass
                elif panel_bg:   # looping animated background in the top panel
                    kp = n_in; args.extend(["-stream_loop", "-1", "-ss", f"{S % 8.0:.3f}", "-i", panel_bg]); n_in += 1
                    f.append(f"[{kp}:v]scale={W}:{TOP_H},trim=0:{(E if E is not None else dur) - S:.3f},setpts=PTS-STARTPTS+{S:.3f}/TB,format=yuv420p[pbg];[sbp][pbg]overlay=0:0:shortest=0[sbq]")
                else: f.append("[sbp]null[sbq]")
                acc = P.get("accent", "#E8603C").lstrip("#")
                if inset: f.append("[sbq]null[sb0]")
                else: f.append(f"[sbq]drawbox=x=0:y={TOP_H - 3}:w={W}:h=6:color=0x{acc}@0.9:t=fill[sb0]")   # accent seam line
                sb = "sb0"
                for i, it in enumerate([x for x in inserts if x.get("mode", "top") == "top"]):
                    if not live(it["t0"], it["t1"]): continue
                    d = it["t1"] - it["t0"]; skip = max(0.0, S - it["t0"]); k = add_input(it["_src"], d=d, ss=((it.get("ss") or 0) + skip) or None)
                    fit = cover(W, TOP_H) if not it.get("contain") else f"scale={W}:{TOP_H}:force_original_aspect_ratio=decrease,pad={W}:{TOP_H}:-1:-1:color=0x121214"
                    f.append(f"[{k}:v]{fit},format=yuva420p,setpts=PTS-STARTPTS+{max(it['t0'], S):.3f}/TB[ti{i}]")
                    f.append(f"[{sb}][ti{i}]overlay=0:0:eof_action=pass:enable='between(t,{it['t0']:.3f},{it['t1']:.3f})'[sb{i + 1}]"); sb = f"sb{i + 1}"
                f.append(f"[{cur}][{sb}]overlay=0:0:enable='{en(top_win)}'[v1]"); cur = "v1"
            else:
                f.append("[bs]nullsink")
            # full-screen cards (style refs 1+2): theme canvas over the whole frame, card graphic on top, no face
            live_cards = [it for it in cards if live(it["t0"], it["t1"])]
            if live_cards:
                kc2 = n_in; args.extend(["-stream_loop", "-1", "-ss", f"{S % 8.0:.3f}", "-i", canvas_bg]); n_in += 1
                f.append(f"[{kc2}:v]scale={W}:{H},trim=0:{(E if E is not None else dur) - S:.3f},setpts=PTS-STARTPTS+{S:.3f}/TB,format=yuv420p[cv2];"
                         f"[{cur}][cv2]overlay=0:0:enable='{en([(c['t0'], c['t1']) for c in cards])}'[vcv]"); cur = "vcv"
                for i, it in enumerate(live_cards):
                    skip = max(0.0, S - it["t0"]); k = add_input(it["_src"], ss=skip or None)
                    f.append(f"[{k}:v]format=yuva420p,setpts=PTS-STARTPTS+{max(it['t0'], S):.3f}/TB[ci{i}]")
                    f.append(f"[{cur}][ci{i}]overlay=0:{int(H * 0.05)}:eof_action=pass:enable='between(t,{it['t0']:.3f},{it['t1']:.3f})'[vci{i}]"); cur = f"vci{i}"
            # full + bubble inserts
            bubbles = [it for it in inserts if it.get("mode") == "bubble"]
            for i, it in enumerate([x for x in inserts if x.get("mode") in ("full", "bubble")]):
                if not live(it["t0"], it["t1"]): continue
                d = it["t1"] - it["t0"]; skip = max(0.0, S - it["t0"]); k = add_input(it["_src"], d=d, ss=((it.get("ss") or 0) + skip) or None)
                kb = f",zoompan=z='min(1+0.0008*on,1.08)':d=1:s={W}x{H}:fps=30" if it.get("kb") and it["_src"].lower().endswith(IMG) else ""
                isimg = it["_src"].lower().endswith(IMG)
                if it.get("fit", "contain" if isimg else "cover") == "contain":  # screenshot: fit inside, blurred copy behind
                    fit = (f"split[fa{i}][fb{i}];[fa{i}]{cover(W, H)},boxblur=40:2,eq=brightness=-0.18[fbg{i}];"
                           f"[fb{i}]scale={int(W * .9)}:{int(H * .9)}:force_original_aspect_ratio=decrease[ffg{i}];[fbg{i}][ffg{i}]overlay=(W-w)/2:(H-h)/2")
                else: fit = cover(W, H)
                f.append(f"[{k}:v]{fit}{kb},format=yuva420p,setpts=PTS-STARTPTS+{max(it['t0'], S):.3f}/TB[fi{i}]")
                f.append(f"[{cur}][fi{i}]overlay=0:0:eof_action=pass:enable='between(t,{it['t0']:.3f},{it['t1']:.3f})'[vf{i}]"); cur = f"vf{i}"
            if bubbles:
                bw = int(W * (0.24 if not reel else 0.42)) // 2 * 2; bh = int(bw * 9 / 16 if not reel else bw * 1.2) // 2 * 2
                mask = os.path.join(work, "bubble_mask.png")
                from PIL import Image, ImageDraw
                im = Image.new("L", (bw, bh), 0); ImageDraw.Draw(im).rounded_rectangle([0, 0, bw - 1, bh - 1], radius=int(bh * 0.12), fill=255); im.save(mask)
                k = add_input(mask, d=dur)
                cw_ = int(W * 0.62) // 2 * 2; ch_ = int(cw_ * bh / bw) // 2 * 2       # crop around the FACE (auto face framing), not the centre
                cx_ = int(min(max(fx * W - cw_ / 2, 0), W - cw_)) // 2 * 2; cy_ = int(min(max(fy * H - ch_ * 0.42, 0), H - ch_)) // 2 * 2
                f.append(f"[bb]crop={cw_}:{ch_}:{cx_}:{cy_},scale={bw}:{bh}[bf];[{k}:v]format=gray,scale={bw}:{bh}[bm];[bf][bm]alphamerge[bub]")
                m = int(W * 0.025)
                f.append(f"[{cur}][bub]overlay={m}:H-h-{m}:enable='{en([(b['t0'], b['t1']) for b in bubbles])}'[vb]"); cur = "vb"
            else:
                f.append("[bb]nullsink")
            # transparent overlays
            for i, ov in enumerate(overlays):
                if not live(ov["t"], ov["t"] + ov["dur"]): continue
                skip = max(0.0, S - ov["t"]); k = add_input(ov["_src"], ss=skip or None)
                f.append(f"[{k}:v]setpts=PTS-STARTPTS+{max(ov['t'], S):.3f}/TB[o{i}]")
                # position: full-frame graphics at 0,0; positioned ones (pfx, wipe, src with x/y) centred on x*W, y*H
                pos = "0:0" if ("x" not in ov) else f"{ov['x'] * W:.0f}-w/2:{ov['y'] * H:.0f}-h/2"
                f.append(f"[{cur}][o{i}]overlay={pos}:eof_action=pass:enable='between(t,{ov['t']:.3f},{ov['t'] + ov['dur']:.3f})'[vo{i}]"); cur = f"vo{i}"
            # captions
            if P.get("captions", reel) and words:  # default: burned captions on reels, off for long-form (upload the .srt instead)
                ass = os.path.join(work, f"captions_{tag}.ass")
                open(ass, "w", encoding="utf-8").write(CAP.build(words, W, H, P.get("caption_y", 0.66 if reel else 0.84), P.get("caption_fs", 70 if reel else 54),
                                                                 3, P.get("caption_acc") or P.get("accent", "#E8603C"), top_win, TOP_H if reel else None, set(P.get("emph", [])),
                                                                 P.get("caption_style", "pill"), [(c["t0"], c["t1"]) for c in cards + [x for x in inserts if x.get("mode") == "full" and x.get("gfx", {}).get("type") in ("device", "checklist", "counter", "diagram", "toon")]],
                                                                 P.get("ink", "#16181D"),
                                                                 light_split=bool(inset and _light(P.get("panel_base", "#F4F2EC"))), key_color=P.get("caption_acc"), stack_y=P.get("stack_y")))
                f.append(f"[{cur}]subtitles=captions_{tag}.ass:fontsdir=fonts[vc]"); cur = "vc"
            if mode == "video": f.append(f"[{cur}]trim=start={S:.3f}:end={E:.3f},setpts=PTS-STARTPTS[vout]")
            elif preview: f.append(f"[{cur}]scale=-2:{540 if reel else 360}[vout]")
            else: f.append(f"[{cur}]null[vout]")


        if mode != "video":
            # ---- audio: voice chain + sfx + music
            # voice: RNNoise (arnndn) neural denoise + residual FFT denoise, de-mud, presence, de-ess, compress
            vc = P.get("voice_clean", True)
            rnn = os.path.join(ROOT, "assets", "rnnoise", (vc if isinstance(vc, str) else "sh") + ".rnnn")
            if vc and os.path.exists(rnn):   # RNNoise model is optional (installer fetches it); fall back to FFT denoise
                shutil.copy(rnn, os.path.join(work, "voice.rnnn"))
                clean = "highpass=f=90,arnndn=m=voice.rnnn:mix=0.9,afftdn=nr=8:nf=-42,"
            elif vc: clean = "highpass=f=90,afftdn=nr=14:nf=-40:tn=1,"
            else: clean = "highpass=f=80,"
            if vc: clean += "equalizer=f=250:t=q:w=1:g=-3,equalizer=f=3500:t=q:w=1.2:g=3,deesser=i=0.4,"
            vin = "[0:a]"
            # background voices / room noise between the speaker's words: a gain envelope from the transcript
            # (speaker's word spans = 1.0, gaps = speech_gate_floor, 40 ms ramps) multiplied onto the voice
            if P.get("speech_gate", True) and words:
                import numpy as np, wave as _w
                sr = 16000; n = int((dur + 0.5) * sr); g = np.full(n, float(P.get("speech_gate_floor", 0.12)))
                for wd in words: g[max(0, int((wd["s"] - 0.10) * sr)):int((wd["e"] + 0.15) * sr)] = 1.0
                k = int(0.04 * sr); g = np.convolve(g, np.ones(k) / k, mode="same")
                with _w.open(os.path.join(work, "gate.wav"), "wb") as fw:
                    fw.setnchannels(1); fw.setsampwidth(2); fw.setframerate(sr); fw.writeframes((g * 32767).astype(np.int16).tobytes())
                kg = add_input(os.path.join(work, "gate.wav"))
                f.append(f"[0:a]aformat=sample_rates=48000:channel_layouts=mono[vmono];[{kg}:a]aresample=48000,aformat=channel_layouts=mono[genv];"
                         f"[vmono][genv]amultiply[vgated]")
                vin = "[vgated]"
            f.append(f"{vin}{clean}acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=3dB,aformat=sample_rates=48000:channel_layouts=stereo[voice]")
            # sound design: every visual beat gets a sound, pre-mixed into one track (sfx_design.py)
            import sfx_design as SFXD
            groups = []
            if words:
                gr = CAP.group(words, 5 if P.get("caption_style") == "duo" else 3, 30 if P.get("caption_style") == "duo" else 16)
                groups = [g[0]["s"] for g in gr if g]
            sev = SFXD.events(inserts, [o for o in overlays if not o.get("_wipe")], punch, words, P.get("sfx_density", "medium"), groups)
            mix = ["[voice]"]
            if sev:
                sw = os.path.join(work, "sfx_mix.wav"); nhit = SFXD.render(sev, dur, os.path.join(ROOT, "assets", "sfx"), sw)
                ks = add_input(sw); f.append(f"[{ks}:a]aformat=sample_rates=48000:channel_layouts=stereo[sfx]"); mix.append("[sfx]")
                print(f"  sound design: {nhit} effects ({nhit / max(dur, 1) * 60:.0f}/min, density {P.get('sfx_density', 'medium')})")
            if P.get("music"):
                mpath = P["music"]
                if mpath.startswith("auto"):  # "auto" or "auto:lofi" -> original track generated to length (music.py)
                    mood = mpath.split(":", 1)[1] if ":" in mpath else "lofi"
                    mpath = os.path.join(work, f"music_{mood}.wav")
                    if not os.path.exists(mpath):
                        subprocess.run([sys.executable, os.path.join(HERE, "music.py"), mpath, "--seconds", f"{dur:.2f}", "--mood", mood], check=True)
                else: mpath = rp(mpath)
                args.extend(["-stream_loop", "-1", "-i", mpath]); n_in += 1; k = n_in - 1
                # every bed is first normalised to -17 LUFS so music_db means the same for any track (generated or user's)
                f.append(f"[{k}:a]atrim=0:{dur:.2f},asetpts=PTS-STARTPTS,loudnorm=I=-17:TP=-2:LRA=11,aresample=48000,volume={P.get('music_db', -24)}dB,afade=t=in:d=1,afade=t=out:st={max(0, dur - 2):.2f}:d=2,aformat=sample_rates=48000:channel_layouts=stereo[mus]")
                f.append("[voice]asplit=2[vk][vsc]"); mix[0] = "[vk]"
                f.append(f"[mus][vsc]sidechaincompress=threshold=0.05:ratio={P.get('duck_ratio', 4)}:attack=15:release=350[duck]"); mix.append("[duck]")
            f.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,alimiter=limit=0.84:level=false[aout]")


        script = os.path.join(work, f"compose_filter_{tag}.txt"); open(script, "w", encoding="utf-8").write(";\n".join(f))
        # veryfast + CRF 18 = same quality as faster + CRF 19 (SSIM 0.98753 vs 0.98765 against a near-lossless reference),
        # 25% faster, ~9% bigger file (measured 2026-11-27 on a 1080x1920 card + face reel)
        x264 = ["-c:v", "libx264", "-preset", "ultrafast" if preview else P.get("preset", "veryfast"), "-crf", "26" if preview else str(P.get("crf", 18)),
                "-pix_fmt", "yuv420p"]
        if mode == "video":
            tail_args = ["-map", "[vout]", "-an"] + x264 + ["-threads", str(threads), "-frames:v", str(nframes), out_path]
        elif mode == "audio":
            tail_args = ["-map", "[aout]", "-vn", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", out_path]
        else:
            tail_args = ["-map", "[vout]", "-map", "[aout]"] + x264 + ["-threads", "0", "-c:a", "aac", "-b:a", "192k",
                         "-movflags", "+faststart", "-t", f"{dur:.3f}", out_path]
        args += ["-/filter_complex", os.path.basename(script), "-progress", f"prog_{tag}.txt", "-stats_period", "1"] + tail_args
        json.dump(args, open(os.path.join(work, f"args_{tag}.json"), "w"))   # exact command, for profiling / debugging
        for attempt in range(3):   # ffmpeg can crash (access violation) when several big jobs run at once: retry
            r = subprocess.run(args, cwd=work)
            if r.returncode == 0: break
            if attempt == 2: raise subprocess.CalledProcessError(r.returncode, args)
            print(f"  ffmpeg exited with {r.returncode} ({tag}) - retrying")


    out = rp(P.get("out", "final.mp4"))
    if preview: out = re.sub(r"\.mp4$", "_preview.mp4", out)
    import time as _t; t0 = _t.time()
    if not any(j for j in jobs): LL.step(base, "graphics", "done", "graphics already made (reused)")
    else: LL.step(base, "graphics", "done", f"{len(jobs)} graphics made")
    for pf in [x for x in os.listdir(work) if x.startswith("prog_")]: os.remove(os.path.join(work, pf))
    LL.step(base, "render", "doing", "rendering", render_dur=dur, out=out)
    LL.step(base, "audio", "doing", "clean voice, music, sound effects")
    nseg = int(P.get("segments", 0) or (0 if (preview or "--single" in a or dur < 20) else min(4, max(2, (os.cpu_count() or 4) // 2))))
    if nseg < 2:
        render("all", out_path=out)
    else:   # split -> render parts in parallel -> join without re-encoding (identical encoder settings)
        from concurrent.futures import ThreadPoolExecutor
        F = int(round(dur * 30)); cuts = [round(F * i / nseg) for i in range(nseg + 1)]
        parts = [(i, cuts[i] / 30, cuts[i + 1] / 30, cuts[i + 1] - cuts[i]) for i in range(nseg)]
        segf = [os.path.join(work, f"seg_{i}.mp4") for i in range(nseg)]; audf = os.path.join(work, "mix.m4a")
        thr = max(1, (os.cpu_count() or 4) // nseg)
        with ThreadPoolExecutor(max_workers=nseg + 1) as ex:
            futs = [ex.submit(render, "video", s0, e0, segf[i], f"s{i}", thr, nf) for i, s0, e0, nf in parts]
            futs.append(ex.submit(render, "audio", 0.0, None, audf, "aud"))
            for fu in futs: fu.result()
        open(os.path.join(work, "segments.txt"), "w").write("".join(f"file '{os.path.basename(x)}'\n" for x in segf))
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "segments.txt", "-i", "mix.m4a",
                        "-map", "0:v", "-map", "1:a", "-c", "copy", "-movflags", "+faststart", "-t", f"{dur:.3f}", out], check=True, cwd=work)
    print(f"  -> {out}  ({_t.time() - t0:.0f}s, {max(nseg, 1)} part{'s' if nseg > 1 else ''})")
    LL.step(base, "render", "done", f"{max(nseg, 1)} parts joined in {_t.time() - t0:.0f} s"); LL.step(base, "audio", "done", "-14 LUFS master")
    LL.step(base, "done", "done", os.path.basename(out), out=out)

if __name__ == "__main__":
    main()
