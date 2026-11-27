"""make_gallery.py - the instant style gallery shown at upload, before any analysis.

    python make_gallery.py [--out <skill>/assets/gallery]      (~1 min, run once; install.ps1 and changes to
                                                               templates re-run it; the images ship with the skill)

Writes, with an illustrated presenter (drawn in code - no real person, no photo):
  styles.jpg         the 3 editing styles, 3 frames each (what the viewer sees at the hook / middle / end)
  looks.jpg          the 4 colour looks (A-D) on the same frame
  style_<id>.jpg     one row per style (mixed, studio, simple)
The intake shows styles.jpg and asks the style straight away, while `autoedit.py --analyze` runs in the background.
The user can still ask to see the looks on their own footage (looks_preview.py) - that is optional now.
"""
import json, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "assets", "fonts")
W, H, TOP = 1080, 1920, 864
F = lambda name, size: ImageFont.truetype(os.path.join(FONTS, name), size)
THEMES = json.load(open(os.path.join(ROOT, "styles", "themes.json"), encoding="utf-8"))
STYLES = json.load(open(os.path.join(ROOT, "styles", "edit_styles.json"), encoding="utf-8"))

def render_all(jobs, tmp):
    """jobs: name -> (params, w, h, t). One browser for everything (render_gfx --batch with stills)."""
    batch = [{"out": os.path.join(tmp, n + ".mov"), "params": p, "w": w, "h": h, "dur": max(t + 0.6, 2.5), "still": t,
              "stillOut": os.path.join(tmp, n + ".png")} for n, (p, w, h, t) in jobs.items()]
    bj = os.path.join(tmp, "jobs.json"); json.dump(batch, open(bj, "w"))
    subprocess.run(["node", os.path.join(HERE, "render_gfx.mjs"), "--batch", bj, "--workers", "4"], check=True, stdout=subprocess.DEVNULL)
    return {n: Image.open(os.path.join(tmp, n + ".png")).convert("RGBA") for n in jobs}

def crop_face(pres, w, h, zoom=1.0):
    """Crop the presenter around the face to w x h (like the auto face framing does)."""
    pw, ph = int(w / zoom), int(h / zoom)
    s = max(pw / W, ph / H); im = pres.resize((int(W * s) + 1, int(H * s) + 1))
    cx, cy = im.width // 2, int(im.height * 0.47)
    box = (max(0, min(im.width - pw, cx - pw // 2)), max(0, min(im.height - ph, cy - ph // 2)))
    return im.crop((box[0], box[1], box[0] + pw, box[1] + ph)).resize((w, h))

def shadow_text(d, xy, txt, font, fill, anchor="la", sh=(0, 0, 0, 150), stroke=0, sc=None):
    x, y = xy
    if sh: d.text((x + 3, y + 5), txt, font=font, fill=sh, anchor=anchor)
    d.text((x, y), txt, font=font, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=sc)

def cap_stack(im, words, key, y=0.56, ink=None):
    d = ImageDraw.Draw(im); x, yy = W * 0.30, H * y
    for i, wd in enumerate(words):
        f = F("ArchivoBlack-Regular.ttf", 98) if i == key else F("Poppins-Bold.ttf", 76)
        shadow_text(d, (x, yy), wd, f, ink or "white", sh=None if ink else (0, 0, 0, 170))
        yy += (112 if i == key else 88)

def cap_duo(im, small, key, acc, y=0.80, ink=None):
    d = ImageDraw.Draw(im)
    shadow_text(d, (W / 2, H * y), small, F("Poppins-Bold.ttf", 60), ink or "white", anchor="mm", sh=None if ink else (0, 0, 0, 140))
    shadow_text(d, (W / 2, H * y + 100), key, F("InstrumentSerif-Italic.ttf", 120), acc, anchor="mm", sh=None if ink else (0, 0, 0, 140))

def cap_karaoke(im, words, hi, acc, y=0.72):
    d = ImageDraw.Draw(im); f = F("Poppins-ExtraBold.ttf", 92)
    txt = " ".join(words); tw = d.textlength(txt, font=f); x = W / 2 - tw / 2
    for i, wd in enumerate(words):
        d.text((x, H * y), wd, font=f, fill=acc if i == hi else "white", anchor="lm", stroke_width=7, stroke_fill="black")
        x += d.textlength(wd + " ", font=f)

def rounded(im, r):
    m = Image.new("L", im.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], r, fill=255)
    out = im.copy(); out.putalpha(m); return out

def inset_frame(card, pres, base):
    im = Image.new("RGBA", (W, H), base)
    im.alpha_composite(card, (0, 40))
    win = rounded(crop_face(pres, W - 120, H - TOP - 140).convert("RGBA"), 48)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([60, TOP + 110, W - 60, H - 30], 48, fill=(0, 0, 0, 70))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18))); im.alpha_composite(win, (60, TOP + 90))
    return im

def split_frame(top, pres):
    im = Image.new("RGBA", (W, H)); im.alpha_composite(top.resize((W, TOP)), (0, 0))
    im.alpha_composite(crop_face(pres, W, H - TOP).convert("RGBA"), (0, TOP)); return im

def sheet(rows, title_font=F("Poppins-Bold.ttf", 34), sub_font=F("Poppins-Medium.ttf", 22), fw=300):
    """rows: [(title, subtitle, [frames])] -> one image, each row = label line + frames side by side."""
    fh = int(fw * H / W); gap = 18; cols = max(len(r[2]) for r in rows)
    sw = cols * fw + (cols + 1) * gap; rh = 96 + fh + gap
    out = Image.new("RGB", (sw, rh * len(rows) + gap), "#FFFFFF"); d = ImageDraw.Draw(out)
    for ri, (t, s, frames) in enumerate(rows):
        y = ri * rh + gap
        d.text((gap, y), t, font=title_font, fill="#16181D"); d.text((gap, y + 44), s, font=sub_font, fill="#5A5F6A")
        for ci, fr in enumerate(frames):
            th = fr.convert("RGB").resize((fw, fh), Image.LANCZOS)
            out.paste(th, (gap + ci * (fw + gap), y + 86))
            d.rounded_rectangle([gap + ci * (fw + gap), y + 86, gap + ci * (fw + gap) + fw - 1, y + 86 + fh - 1], 14, outline="#D9D6CE", width=2)
    return out

def wrap(s, n=60):
    out, line = [], ""
    for w_ in s.split():
        if len(line) + len(w_) + 1 > n: out.append(line); line = w_
        else: line = (line + " " + w_).strip()
    return " ".join(out + [line]) if len(" ".join(out + [line])) <= n else (out + [line])[0] + "..."

def main():
    a = sys.argv[1:]
    out = a[a.index("--out") + 1] if "--out" in a else os.path.join(ROOT, "assets", "gallery")
    os.makedirs(out, exist_ok=True); tmp = tempfile.mkdtemp(prefix="gallery_")
    P = THEMES["paper"]; acc_blue = "#2F6FED"
    jobs = {
        "p_warm": ({"type": "presenter", "room": "warm"}, W, H, 0.5),
        "p_plain": ({"type": "presenter", "room": "plain", "shirt": "#2F4858"}, W, H, 0.5),
        "p_low": ({"type": "presenter", "room": "plain", "shirt": "#2F4858", "fy": 0.6}, W, H, 0.5),
        # Clean cards (paper look)
        "m_title": ({"type": "title", "theme": "paper", "l1": "How I edit", "money": "in 5 minutes", "l2": "with free AI tools", "k": 1.35}, W, int(H * .72), 2.0),
        "m_diag": ({"type": "diagram", "theme": "paper", "head": "What it does", "items": "Your video|AI editor", "icons": "video|sparkles",
                    "op": "+", "result": "Finished reel", "ricon": "check", "step": "2/4", "k": 1.35}, W, TOP, 2.4),
        "m_sticker": ({"type": "sticker", "icon": "smartphone", "label": "My phone", "color": acc_blue}, 540, 368, 0.6),
        # Bold B-roll
        "s_top": ({"type": "device", "kind": "laptop", "head": "My editing day", "label": "Time spent editing", "value": "2 hours",
                   "rows": "Cutting pauses:45 min|Captions:40 min", "pct": 90, "cy": 0.40, "maxh": 0.62}, W, TOP, 1.6),
        "s_band": ({"type": "band", "l1": "2 hours editing a day", "l2": "so I built my own AI editor", "y": 0.45}, W, H, 1.2),
        "s_dev": ({"type": "device", "kind": "phone", "head": "Auto cut", "sub": "This video", "label": "Video length", "value": "78 s to 54 s",
                   "rows": "Pauses cut:23|Retakes cut:3", "pct": 70, "cy": 0.38, "maxh": 0.64, "dx": 0.11}, W, H, 1.8),
        "s_num": ({"type": "bignum", "n": "2"}, W, H, 1.0),
        "s_cta": ({"type": "ctaword", "word": "Editor", "y": 0.72}, W, H, 1.2),
        # Face and captions
        "f_title": ({"type": "title", "theme": "paper", "l1": "How I edit", "money": "in 5 minutes", "l2": "with free AI tools", "k": 1.25}, W, TOP, 2.0),
        "f_counter": ({"type": "counter", "theme": "paper", "value": "5 min", "caption": "to a finished reel", "k": 1.2}, W, H, 2.2),
    }
    for k in ("paper", "highlight", "navy", "mint"):
        jobs["look_" + k] = ({"type": "diagram", "theme": k, "head": "Step 1: your main point", "items": "Idea|Action", "icons": "lightbulb|zap",
                              "op": "+", "result": "The result", "ricon": "trophy", "k": 1.35}, W, TOP, 2.4)
    G = render_all(jobs, tmp)
    warm, plain = G["p_warm"], G["p_plain"]

    # --- Clean cards: full card / card + face window / face + sticker
    m1 = Image.new("RGBA", (W, H), P["panel_base"]); m1.alpha_composite(G["m_title"], (0, int(H * .05)))
    cap_duo(m1, "so I built my own", "AI editor", acc_blue, y=0.84, ink="#16181D")
    m2 = inset_frame(G["m_diag"], plain, P["panel_base"]); cap_duo(m2, "it does the", "boring part", "#FFE45C", y=0.84)
    m3 = crop_face(plain, W, H).convert("RGBA"); st = G["m_sticker"]; m3.alpha_composite(st, (int(W * .76 - st.width / 2), int(H * .30 - st.height / 2)))
    cap_duo(m3, "I record on", "my phone", "#FFE45C", y=0.84)
    # --- Bold B-roll: hook band / big number over a phone / glowing CTA
    s1 = split_frame(G["s_top"], warm); s1.alpha_composite(G["s_band"]); cap_stack(s1, ["so", "I", "built"], 2, y=0.64)
    s2 = Image.new("RGBA", (W, H)); s2.alpha_composite(G["s_dev"]); s2.alpha_composite(G["s_num"]); cap_stack(s2, ["it", "cuts", "my", "pauses"], 3, y=0.72, ink="#16181D")
    s3 = warm.copy(); s3.alpha_composite(G["s_cta"])
    # --- Face and captions: face + chapter word / punch-in + karaoke / counter
    f1 = G["p_low"].copy(); f1.alpha_composite(G["f_title"], (0, 0))
    f2 = crop_face(plain, W, H, zoom=1.25).convert("RGBA"); cap_karaoke(f2, ["THE", "BORING", "PART"], 1, "#FFE45C")
    f3 = Image.new("RGBA", (W, H), P["panel_base"]); f3.alpha_composite(G["f_counter"], (0, -int(H * .08)))
    ImageDraw.Draw(f3).text((W / 2, H * .74), "5 MINUTES LATER", font=F("Poppins-ExtraBold.ttf", 92), fill="#16181D", anchor="mm")

    rows = {"mixed": [m1, m2, m3], "studio": [s1, s2, s3], "simple": [f1, f2, f3]}
    order = ["studio", "mixed", "simple"]
    for k in order:
        sheet([(STYLES[k]["label"], STYLES[k]["tagline"], rows[k])]).save(os.path.join(out, f"style_{k}.jpg"), quality=90)
    sheet([(f"{chr(65 + i)}  {STYLES[k]['label']}", STYLES[k]["tagline"], rows[k]) for i, k in enumerate(order)]).save(
        os.path.join(out, "styles.jpg"), quality=90)
    looks = []
    for k in ("paper", "highlight", "navy", "mint"):
        fr = inset_frame(G["look_" + k], plain, THEMES[k]["panel_base"]); cap_duo(fr, "your", "main point", THEMES[k]["accent"], y=0.84)
        looks.append(fr)
    sheet([("Colour looks (Clean cards and Face and captions)", "A Clean Paper   B Highlighter Yellow   C Navy & Gold   D Mint Fresh", looks)],
          fw=260).save(os.path.join(out, "looks.jpg"), quality=90)
    print("  ->", out)

if __name__ == "__main__":
    main()
