"""captions.py - house-style caption pills (ASS) from words_cut.json.

    python captions.py words_cut.json out.ass --w 1080 --h 1920 [--y 0.66] [--fs 70] [--max-words 3]
                       [--acc "#E8603C"] [--split "0-2.5,10.2-14"] [--seam 864] [--emph "claude,chatgpt"] [--style pill|bold|minimal|duo|stack]

Style (decided for this channel): white bold caps, 1-3 words, inside a rounded orange pill, pop-in.
Money, numbers and tool names get a bigger pill. During --split windows (split-stack layout) the
pill sits on the seam between the top graphic and the face (y = --seam px); otherwise at --y * h.
Burn with ffmpeg:  subtitles=out.ass:fontsdir=<skill>/assets/fonts   (run ffmpeg from the .ass folder)
"""
import json, os, re, sys
from PIL import ImageFont
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "..", "assets", "fonts", "Poppins-Bold.ttf")
TOOLS = {"claude", "chatgpt", "gpt", "gemini", "grok", "midjourney", "canva", "notion", "zapier", "n8n", "make",
         "perplexity", "copilot", "cursor", "lovable", "elevenlabs", "heygen", "capcut", "openai", "anthropic"}

def ass_time(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def ass_color(hexc, alpha="00"):
    h = hexc.lstrip("#"); return f"&H{alpha}{h[4:6]}{h[2:4]}{h[0:2]}&"

PILL_INK = r"\1c&H1D1816&"   # dark words on a light pill (yellow, lime, white)

def light(hexc):
    h = hexc.lstrip("#"); r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b > 165

def pill(w, h):
    r = h / 2
    return (f"m {r:.0f} 0 l {w - r:.0f} 0 b {w:.0f} 0 {w:.0f} {h:.0f} {w - r:.0f} {h:.0f} "
            f"l {r:.0f} {h:.0f} b 0 {h:.0f} 0 0 {r:.0f} 0")

def clean(w):
    w = w.strip()
    w = re.sub(r"^[\"'(\[]+|[\"')\],;:]+$", "", w)
    w = re.sub(r"(?<!\d)[.]+$", "", w)
    return w.upper()

def is_emph(w, extra):
    b = re.sub(r"[^a-z0-9$]", "", w.lower())
    return bool(re.search(r"\d|\$", w)) or b in TOOLS or b in extra

def group(words, max_words=3, max_chars=16):
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        txt = " ".join(clean(x["w"]) for x in cur)
        end_punct = re.search(r"[.!?,:;]$", w["w"].strip())
        long_gap = nxt and nxt["s"] - w["e"] > 0.35
        too_long = nxt and len(txt) + 1 + len(clean(nxt["w"])) > max_chars
        if len(cur) >= max_words or end_punct or long_gap or too_long or not nxt:
            out.append(cur); cur = []
    return out

def build(words, W, H, y=0.66, fs=70, max_words=3, acc="#E8603C", split=(), seam=None, emph=(), style="pill", cards=(), ink="#16181D", light_split=False, key_color=None, stack_y=None):
    """style: pill | bold (white caps, black outline, active word in accent) | minimal (sentence case, soft shadow)
    | duo (style refs: small plain words + the key phrase on its own line in big italic serif, accent colour).
    cards: windows with a full-screen card on screen - captions move low (y 0.86) and use dark `ink` text."""
    tt = TTFont(FONT); os2 = tt["OS/2"]; upm = tt["head"].unitsPerEm
    em_ratio = upm / (os2.usWinAscent + os2.usWinDescent)   # libass sizes by win ascent+descent
    groups = group(words, 5 if style == "duo" else 4 if style == "stack" else max_words, 30 if style == "duo" else 34 if style == "stack" else 16)
    if style == "duo":   # a caption never ends on "a", "the", "to"...: move those words to the start of the next one
        SM = {"a", "an", "the", "to", "of", "in", "on", "at", "and", "or", "it", "is", "i", "my", "your", "with", "for", "this", "that"}
        for gi in range(len(groups) - 1):
            while len(groups[gi]) > 1 and re.sub(r"[^a-z]", "", groups[gi][-1]["w"].lower()) in SM and not re.search(r"[.!?,]$", groups[gi][-1]["w"]):
                groups[gi + 1].insert(0, groups[gi].pop())
    ev = []
    for gi, g in enumerate(groups):
        text = " ".join(clean(x["w"]) for x in g).strip()
        if not text: continue
        s = g[0]["s"]
        e = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else g[-1]["e"] + 0.3
        e = min(e, g[-1]["e"] + 0.6); e = max(e, s + 0.25)
        big = any(is_emph(x["w"], emph) for x in g)
        size = round(fs * (1.22 if big else 1.0))
        font = ImageFont.truetype(FONT, max(8, round(size * em_ratio)))
        tw = font.getlength(text)
        ph = size * em_ratio * 1.55; pw = tw + size * em_ratio * 0.9
        # cut the event at layout changes so the pill jumps with the layout (pop only on the first piece)
        cuts = sorted({s, e, *[b for lo, hi in list(split) + list(cards) for b in (lo, hi) if s < b < e]})
        x = W / 2
        for pi, (s0, e0) in enumerate(zip(cuts, cuts[1:])):
            insplit = any(lo <= (s0 + e0) / 2 < hi for lo, hi in split)
            oncard = any(lo <= (s0 + e0) / 2 < hi for lo, hi in cards)
            cy = 0.86 * H if oncard else seam if (insplit and seam) else y * H
            pop = r"\fscx72\fscy72\t(0,90,\fscx108\fscy108)\t(90,170,\fscx100\fscy100)" if pi == 0 else ""
            if style == "pill":
                ev.append(f"Dialogue: 0,{ass_time(s0)},{ass_time(e0)},Pill,,0,0,0,,{{\\an5\\pos({x:.0f},{cy:.0f})\\bord0\\shad0\\1c{ass_color(acc)}\\1a&H10&{pop}\\p1}}{pill(pw, ph)}")
                ev.append(f"Dialogue: 1,{ass_time(s0)},{ass_time(e0)},Cap,,0,0,0,,{{\\an5\\pos({x:.0f},{cy + size * 0.04:.0f})\\fs{size}{pop}{PILL_INK if light(acc) else ''}}}{text}")
            elif style == "bold":  # one event per spoken word: that word in the accent colour (karaoke look)
                toks = [clean(x["w"]) for x in g]
                for wi, wd in enumerate(g):
                    ws = s0 if wi == 0 else max(s0, wd["s"])
                    we = min(e0, g[wi + 1]["s"]) if wi + 1 < len(g) else e0
                    if we - ws < 0.02: continue
                    line = " ".join((f"{{\\1c{ass_color(acc)}}}{t}{{\\1c&HFFFFFF&}}" if k == wi else t) for k, t in enumerate(toks))
                    pp = pop if wi == 0 else ""
                    ev.append(f"Dialogue: 1,{ass_time(ws)},{ass_time(we)},Bold,,0,0,0,,{{\\an5\\pos({x:.0f},{cy:.0f})\\fs{round(size * 1.15)}{pp}}}{line}")
            elif style == "duo":
                raw = [x["w"].strip() for x in g]
                # key phrase = the last 1-2 real words (not "a", "the", "to"...); small words never end a key line
                SMALL = {"a", "an", "the", "to", "of", "in", "on", "at", "and", "or", "it", "is", "i", "my", "your", "with", "for", "this", "that"}
                core = [re.sub(r"[^a-z0-9$]", "", r.lower()) for r in raw]
                end = len(raw)
                while end > 0 and core[end - 1] in SMALL: end -= 1
                if len(raw) >= 3 and end >= 2 and end == len(raw):
                    st = end - 2 if core[end - 2] not in SMALL else end - 1
                    small, key = " ".join(raw[:st]), " ".join(raw[st:])
                elif any(is_emph(x["w"], emph) for x in g):
                    small, key = "", " ".join(raw)
                else:
                    small, key = " ".join(raw), ""
                dark = oncard or (insplit and light_split)   # light canvas behind (card, or the inset window page): dark small words
                c_small = ass_color(ink) if dark else "&H00FFFFFF&"
                sh = r"\shad0\bord0" if dark else ""
                fade = r"\fad(90,0)" if pi == 0 else ""
                txt = ("{" + rf"\fs{round(size * 0.85)}\1c{c_small}" + "}" + small) if small else ""
                if key:   # the key phrase is the big line (style refs: ~2x the small words)
                    txt += (r"\N" if small else "") + "{" + rf"\fnInstrument Serif\i1\b0\fs{round(size * 1.6)}\1c{ass_color(acc)}" + "}" + key
                ev.append(f"Dialogue: 1,{ass_time(s0)},{ass_time(e0)},Duo,,0,0,0,," + "{" + rf"\an5\pos({x:.0f},{cy:.0f}){sh}{fade}" + "}" + txt)
            elif style == "stack":  # ref 7: words pile up one per line, left-aligned; the key word bigger in heavy type
                raw = [re.sub(r"^[\"'(\[]+|[\"')\]]+$", "", x["w"].strip()).lower() for x in g]
                core = [re.sub(r"[^a-z0-9$]", "", r) for r in raw]
                key = max(range(len(raw)), key=lambda k: (is_emph(g[k]["w"], emph), len(core[k]))) if raw else -1
                if len(core[key]) < 4 and not is_emph(g[key]["w"], emph): key = -1
                bx = W * 0.30; by = (0.72 * H if oncard else 0.62 * H if (insplit and seam) else (stack_y or 0.56) * H)   # split: below the hook band
                for wi, wd in enumerate(g):
                    ws = s0 if wi == 0 else max(s0, wd["s"])
                    we = min(e0, g[wi + 1]["s"]) if wi + 1 < len(g) else e0
                    if we - ws < 0.02: continue
                    lines = []
                    for k in range(wi + 1):
                        fnt = (rf"\fnArchivo Black\b0\fs{round(size * 1.4)}" + (rf"\1c{ass_color(key_color)}" if key_color and not oncard else "") if k == key else rf"\fnPoppins\b1\fs{round(size * 1.1)}")
                        pp = r"\fscx70\fscy70\t(0,110,\fscx100\fscy100)" if (k == wi and pi == 0) else ""
                        lines.append("{" + fnt + pp + "}" + raw[k])
                    ink_tag = (rf"\1c{ass_color(ink)}\bord0\shad0" if oncard else "")
                    ev.append(f"Dialogue: 1,{ass_time(ws)},{ass_time(we)},Stack,,0,0,0,," + "{" + rf"\an7\pos({bx:.0f},{by:.0f}){ink_tag}" + "}" + r"\N".join(lines))
            else:  # minimal: sentence case, soft shadow
                txt = " ".join(x["w"].strip() for x in g)
                ev.append(f"Dialogue: 1,{ass_time(s0)},{ass_time(e0)},Min,,0,0,0,,{{\\an5\\pos({x:.0f},{cy:.0f})\\fs{round(size * 0.85)}}}{txt}")
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Poppins,{fs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: Pill,Poppins,{fs},{ass_color(acc)},&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: Bold,Poppins ExtraBold,{fs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{max(3, fs // 14)},2,5,0,0,0,1
Style: Duo,Poppins,{fs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,0,{max(3, fs // 14)},5,0,0,0,1
Style: Stack,Poppins,{fs},&H00FFFFFF,&H00FFFFFF,&H30101010,&H70000000,-1,0,0,0,100,100,0,0,1,{max(3, fs // 20)},{max(3, fs // 16)},7,0,0,0,1
Style: Min,Poppins,{fs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,0,0,0,0,100,100,0,0,1,0,{max(2, fs // 22)},5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return head + "\n".join(ev) + "\n"

def main():
    a = sys.argv[1:]
    if len(a) < 2: print(__doc__); sys.exit(1)
    g = lambda k, d: a[a.index(k) + 1] if k in a else d
    split = [tuple(map(float, r.split("-"))) for r in g("--split", "").split(",") if r.strip()]
    emph = {x.strip().lower() for x in g("--emph", "").split(",") if x.strip()}
    words = json.load(open(a[0], encoding="utf-8"))
    W, H = int(g("--w", 1080)), int(g("--h", 1920))
    seam = float(g("--seam", 0)) or None
    open(a[1], "w", encoding="utf-8").write(build(words, W, H, float(g("--y", 0.66)), int(g("--fs", 70)),
                                                  int(g("--max-words", 3)), g("--acc", "#E8603C"), split, seam, emph, g("--style", "pill")))
    print("  ->", a[1])

if __name__ == "__main__":
    main()
