"""looks_preview.py - one still per colour look, made from the user's own video, for the intake question.

    python looks_preview.py <name>_edit [--looks paper,highlight,navy,mint] [--t 0.4]

Writes <name>_edit/looks.jpg (side by side, labelled A, B, C, D) using cut.mp4 (or the source) at --t of its length:
the split-stack reel frame with that look's panel background, a sample diagram, the seam line and a caption.
~30-60 s on a laptop. Show it to the user right before asking the "Look" question.
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import captions as CAP

def sh(args): subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    work = os.path.abspath(a[0]); g = lambda k, d: a[a.index(k) + 1] if k in a else d
    looks = g("--looks", "paper,highlight,navy,mint").split(",")
    themes = json.load(open(os.path.join(ROOT, "styles", "themes.json"), encoding="utf-8"))
    an = json.load(open(os.path.join(work, "analysis.json"), encoding="utf-8"))
    vid = os.path.join(work, "cut.mp4") if os.path.exists(os.path.join(work, "cut.mp4")) else an["file"]
    wj = os.path.join(work, "words_cut.json") if os.path.exists(os.path.join(work, "words_cut.json")) else os.path.join(work, "words.json")
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vid]).decode())
    t = dur * float(g("--t", 0.4))
    W, H, TOP = 1080, 1920, 864
    tmp = os.path.join(work, "_looks"); os.makedirs(tmp, exist_ok=True)
    face = os.path.join(tmp, "face.png"); fy = 0.45
    sh(["ffmpeg", "-nostdin", "-y", "-ss", f"{t:.2f}", "-i", vid, "-frames:v", "1", "-vf",
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},crop={W}:{H - TOP}:0:'max(0,min(ih-{H - TOP},ih*{fy}-{(H - TOP) * .45}))'", face])
    words = json.load(open(wj, encoding="utf-8"))
    near = [w for w in words if w["s"] >= t][:3] or words[:3]
    cap_words = [{"w": w["w"], "s": 0.0 + i * 0.3, "e": 0.3 + i * 0.3} for i, w in enumerate(near)]
    tiles = []
    for i, lk in enumerate(looks):
        th = themes[lk]
        bg = os.path.join(tmp, f"bg_{lk}.png"); gx = os.path.join(tmp, f"gx_{lk}.png")
        sh(["node", os.path.join(HERE, "render_gfx.mjs"), "x", json.dumps({"style": th["panel_bg_style"], "acc": th["accent"], "base": th["panel_base"]}),
            "--template", "motionbg.html", "--w", str(W), "--h", str(TOP), "--dur", "8", "--still", "2", bg])
        sh(["node", os.path.join(HERE, "render_gfx.mjs"), "x", json.dumps({"type": "diagram", "theme": th["theme"], "head": "Step 1: your main point",
            "items": "Idea|Action", "icons": "lightbulb|rocket", "op": "+", "result": "The result", "ricon": "check-circle", "k": 1.35}),
            "--w", str(W), "--h", str(TOP), "--dur", "3", "--still", "2.5", gx])
        frame = Image.new("RGB", (W, H)); frame.paste(Image.open(bg).convert("RGB"), (0, 0))
        bgk = an.get("background") or {}
        if bgk.get("keyable"):   # show the real background swapped for this look's animated backdrop
            fb = os.path.join(tmp, f"fb_{lk}.png"); fk = os.path.join(tmp, f"fk_{lk}.png"); kc = bgk["key"].lstrip("#")
            sh(["node", os.path.join(HERE, "render_gfx.mjs"), "x", json.dumps({"style": th["panel_bg_style"], "acc": th["accent"], "base": th["panel_base"]}),
                "--template", "motionbg.html", "--w", str(W), "--h", str(H - TOP), "--dur", "8", "--still", "3", fb])
            keyf = (f"chromakey=0x{kc}:0.12:0.08,despill=type={'green' if bgk['kind'] == 'green_screen' else 'blue'}"
                    if bgk["kind"].endswith("screen") else f"colorkey=0x{kc}:0.14:0.08")
            sh(["ffmpeg", "-nostdin", "-y", "-i", fb, "-i", face, "-filter_complex", f"[1]format=yuva420p,{keyf}[k];[0][k]overlay", fk])
            frame.paste(Image.open(fk).convert("RGB"), (0, TOP))
        elif os.path.exists(os.path.join(work, "matte", "core.png")):   # matte-assisted swap (wall close to skin colour)
            import numpy as np
            full = os.path.join(tmp, "full.png")
            if not os.path.exists(full):
                sh(["ffmpeg", "-nostdin", "-y", "-ss", f"{t:.2f}", "-i", vid, "-frames:v", "1", "-vf",
                    f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}:'(iw-{W})*0.5':'(ih-{H})*{max(0, fy - 0.1)}'", full])
            fbf = os.path.join(tmp, f"fbf_{lk}.png")
            sh(["node", os.path.join(HERE, "render_gfx.mjs"), "x", json.dumps({"style": th["panel_bg_style"], "acc": th["accent"], "base": th["panel_base"]}),
                "--template", "motionbg.html", "--w", str(W), "--h", str(H), "--dur", "8", "--still", "3", fbf])
            px = np.asarray(Image.open(full).convert("RGB")).astype(float)
            key = np.array([int(bgk["key"][i:i + 2], 16) for i in (1, 3, 5)], float)
            ka = np.clip((np.linalg.norm(px - key, axis=2) / 441 - 0.14) / 0.08, 0, 1)          # ~ ffmpeg colorkey 0.14:0.08
            core = np.asarray(Image.open(os.path.join(work, "matte", "core.png")).convert("L").resize((W, H))) / 255
            outer = np.asarray(Image.open(os.path.join(work, "matte", "outer.png")).convert("L").resize((W, H))) / 255
            al = Image.fromarray((np.maximum(ka, core) * outer * 255).astype(np.uint8))
            comp = Image.composite(Image.open(full).convert("RGB"), Image.open(fbf).convert("RGB").resize((W, H)), al)
            ytop = int(max(0, min(H - (H - TOP), H * fy - (H - TOP) * .45)))
            frame.paste(comp.crop((0, ytop, W, ytop + H - TOP)), (0, TOP))
        else:
            frame.paste(Image.open(face).convert("RGB"), (0, TOP))
        top = Image.open(gx).convert("RGBA"); frame.paste(top, (0, 0), top)
        d = ImageDraw.Draw(frame); acc = th["accent"]
        d.rectangle([0, TOP - 3, W, TOP + 3], fill=acc)
        raw = os.path.join(tmp, f"raw_{lk}.png"); frame.save(raw)
        ass = os.path.join(tmp, f"cap_{lk}.ass")
        open(ass, "w", encoding="utf-8").write(CAP.build(cap_words, W, H, 0.8, 70, 3, acc, [(0, 9)], TOP, set(), "bold" if lk != "mint" else "pill"))
        fonts = os.path.join(ROOT, "assets", "fonts")
        import shutil; shutil.copytree(fonts, os.path.join(tmp, "fonts_l"), dirs_exist_ok=True)
        out = os.path.join(tmp, f"look_{lk}.png")
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", os.path.basename(raw), "-vf",
                        f"subtitles={os.path.basename(ass)}:fontsdir=fonts_l,scale=360:-1", "-frames:v", "1", os.path.basename(out)],
                       cwd=tmp, check=True)
        im = Image.open(out).convert("RGB"); lab = Image.new("RGB", (im.width, im.height + 70), (24, 24, 28))
        lab.paste(im, (0, 70)); dl = ImageDraw.Draw(lab)
        f = ImageFont.truetype(os.path.join(fonts, "Poppins-Bold.ttf"), 24)
        dl.text((14, 8), f"{chr(65 + i)}  {th['label']}", font=f, fill=(255, 255, 255))
        dl.text((14, 40), f"like {th['looks_like']}", font=ImageFont.truetype(os.path.join(fonts, "Poppins-Medium.ttf"), 16), fill=(170, 170, 180))
        tiles.append(lab)
    sheet = Image.new("RGB", (sum(t.width for t in tiles) + 12 * (len(tiles) - 1), tiles[0].height), (24, 24, 28))
    x = 0
    for tl in tiles: sheet.paste(tl, (x, 0)); x += tl.width + 12
    out = os.path.join(work, "looks.jpg"); sheet.save(out, quality=90)
    print("  ->", out)

if __name__ == "__main__":
    main()
