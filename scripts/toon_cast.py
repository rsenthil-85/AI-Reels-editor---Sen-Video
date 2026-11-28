"""toon_cast.py - a cartoon cast of its own for every video (the cartoon cut-aways, templates/toon/).

    python toon_cast.py <edit folder> [--hair side|short|curly|spiky|bald|bun|long] [--beard none|stubble|full|moustache]
                        [--glasses] [--hair-colour "#2B211D"] [--seed N]

Writes <edit>/toon_cast.json, which compose.py passes to every `type: toon` graphic of that video:
  - the presenter looks like the speaker: skin tone and shirt colour are sampled from the video (face position from
    face.json), turned into flat cartoon colours. Hair, beard and glasses can't be read reliably by a script: the agent
    looks at sheet.jpg and passes them (--hair curly --beard stubble ...). Unset ones come from the seed.
  - the helper robot, the room palette, the wall decor and the prop colour are picked by a seed made from the video's
    name, so every video gets its own look and re-renders of the same video stay the same.
Standard library + ffmpeg only.
"""
import colorsys, hashlib, json, os, random, subprocess, sys

SKINS = [("#F7D7BC", "#E3B394"), ("#F2C7A0", "#DDA37C"), ("#E3AC80", "#C98C60"), ("#CC915F", "#AD7346"),
         ("#A8704A", "#8A5638"), ("#87563A", "#6B402A"), ("#6A4230", "#523022")]
HAIRS = ["side", "short", "curly", "spiky", "bun", "long", "bald"]
BOTS = [  # body, head, face, eyes, accent
    {"body": "#B5C8DE", "head": "#FBF6EA", "face": "#1B5753", "eye": "#8ACFC6", "acc": "#E4613F"},
    {"body": "#E8B43A", "head": "#FBF6EA", "face": "#2B2420", "eye": "#F3D37F", "acc": "#3FA7A0"},
    {"body": "#A7AE5B", "head": "#F4EAD5", "face": "#3B4766", "eye": "#B5C8DE", "acc": "#E4613F"},
    {"body": "#F0917A", "head": "#FBF6EA", "face": "#257A74", "eye": "#CBD08E", "acc": "#E8B43A"},
    {"body": "#8ACFC6", "head": "#C9CFCB", "face": "#6E4A6B", "eye": "#F0B4A8", "acc": "#E8B43A"},
    {"body": "#C9CFCB", "head": "#FBF6EA", "face": "#B8452B", "eye": "#F3D37F", "acc": "#3FA7A0"},
]
PALETTES = 5            # room colour sets, defined in templates/toon/scenes.js
DECOR = ["window", "frame", "plant", "lamp", "shelf", "clockwall"]
PROPS = ["#A7AE5B", "#E4613F", "#3FA7A0", "#E8B43A", "#7F9CC0", "#6E4A6B"]

def hx(rgb): return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(c)))) for c in rgb)

def median(vals):
    v = sorted(vals); return v[len(v) // 2] if v else 0

def sample(frame_rgb, W, H, cx, cy, rw, rh, pct=0.5):
    px = []
    for y in range(max(0, int((cy - rh) * H)), min(H, int((cy + rh) * H))):
        for x in range(max(0, int((cx - rw) * W)), min(W, int((cx + rw) * W))):
            i = (y * W + x) * 3; px.append(frame_rgb[i:i + 3])
    if not px: return None
    if pct != 0.5:   # e.g. the lit side of a face: the pixel at this brightness rank
        px.sort(key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]); return tuple(px[int(pct * (len(px) - 1))])
    return tuple(median([p[k] for p in px]) for k in range(3))

def grab(video, t):
    W, H = 180, 320
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                          "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout
    return (raw, W, H) if len(raw) == W * H * 3 else None

def cartoon_skin(rgb):
    lum = lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
    def to_rgb(h): return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
    # phone footage is often dim or yellow-lit: match on brightness, a little brighter than measured
    target = min(255, lum(rgb) * 1.1)
    return min(SKINS, key=lambda s: abs(lum(to_rgb(s[0])) - target))

def cartoon_colour(rgb):
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    if s < 0.14:                     # white / grey / black clothes: keep them neutral, just readable on paper
        v = min(max(v, 0.32), 0.88); s = 0.06
    else:
        s = min(max(s * 1.15, 0.38), 0.72); v = min(max(v * 1.1, 0.48), 0.86)
    main = colorsys.hsv_to_rgb(h, s, v); dark = colorsys.hsv_to_rgb(h, min(1, s + 0.08), v * 0.78)
    return hx([c * 255 for c in main]), hx([c * 255 for c in dark])

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    ed = os.path.abspath(a[0]); g = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    try: live = json.load(open(os.path.join(ed, "live.json"), encoding="utf-8"))
    except Exception: live = {}
    name = live.get("video") or os.path.basename(ed)
    seed = int(g("--seed") or int(hashlib.sha1(name.encode()).hexdigest()[:8], 16))
    R = random.Random(seed)
    cast = {"seed": seed, "pal": R.randrange(PALETTES), "bot": dict(R.choice(BOTS), shape=R.choice(["round", "square", "dome"]),
            antenna=R.choice(["ball", "ears", "bolt"])), "decor": R.sample(DECOR, 2), "prop": R.choice(PROPS),
            "hairStyle": R.choice(HAIRS[:6]), "hair": "#2B211D", "beard": R.choice(["none", "none", "stubble", "moustache"]),
            "glasses": R.random() < 0.25, "skin": SKINS[1][0], "skinD": SKINS[1][1], "shirt": "#E4613F", "shirtD": "#B8452B",
            "from_video": False}
    # the speaker: skin and shirt from a frame of the cut (or the source) at the face position
    try: face = json.load(open(os.path.join(ed, "face.json"), encoding="utf-8"))
    except Exception: face = {}
    fx, fy = face.get("face_x", 0.5), face.get("face_y", 0.42)
    chin = fy + (fy - face["head_top"]) if face.get("head_top") else fy + 0.22   # the head is about as tall below its centre as above
    vid = os.path.join(ed, "cut.mp4") if os.path.exists(os.path.join(ed, "cut.mp4")) else live.get("src")
    if vid and os.path.exists(vid):
        try:
            d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vid]).decode())
        except Exception: d = 4
        skins, shirts = [], []
        for t in (d * 0.25, d * 0.5, d * 0.75):
            fr = grab(vid, t)
            if not fr: continue
            raw, W, H = fr
            s = sample(raw, W, H, fx, fy + 0.02, 0.05, 0.04, pct=0.75)        # cheeks and nose, the lit side
            c = None   # the shirt: going down from the chin, the first patches that are not skin (orange-brown) or shadow
            def skinlike(px):
                h, sa, v = colorsys.rgb_to_hsv(*(q / 255 for q in px))
                lit = lambda q: 0.299 * q[0] + 0.587 * q[1] + 0.114 * q[2]
                if lit(px) > lit(s) * 1.25: return False          # cream / beige clothes: same hue as skin, much lighter
                return (h * 360 < 48 or h * 360 > 345) and sa > 0.28
            y, found = chin, []
            while y < 0.98 and len(found) < 2:
                q = sample(raw, W, H, fx, y, 0.10, 0.02)
                if q and not skinlike(q) and max(q) > 28: found.append(q)
                elif found: break
                y += 0.025
            if found: c = tuple(median([x[k] for x in found]) for k in range(3))
            if s: skins.append(s)
            if c: shirts.append(c)
        if skins:
            s = tuple(median([x[k] for x in skins]) for k in range(3)); cast["skin"], cast["skinD"] = cartoon_skin(s)
            cast["from_video"] = True
        if shirts:
            c = tuple(median([x[k] for x in shirts]) for k in range(3)); cast["shirt"], cast["shirtD"] = cartoon_colour(c)
    # what the agent saw on the frame wins
    if g("--hair"): cast["hairStyle"] = g("--hair")
    if g("--beard"): cast["beard"] = g("--beard")
    if "--glasses" in a: cast["glasses"] = True
    if "--no-glasses" in a: cast["glasses"] = False
    if g("--hair-colour"): cast["hair"] = g("--hair-colour")
    json.dump(cast, open(os.path.join(ed, "toon_cast.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps(cast))

if __name__ == "__main__":
    main()
