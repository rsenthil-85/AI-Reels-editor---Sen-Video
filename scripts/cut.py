"""cut.py - jump-cut a talking-head recording from its words.json: dead air, fillers, retakes.

    python cut.py input.mp4 words.json out_dir [--gap 0.30] [--pad 0.07] [--drop "12.3-15.0,40-42.5"] [--keep-fillers] [--dry]

- Any silence longer than --gap between words is cut, leaving --pad of breath on each side.
- Isolated fillers (um, uh, erm, hmm, ah) are dropped unless --keep-fillers.
- Retakes are found automatically (a phrase restarted within 12 s: the earlier take is cut, the last kept;
  "I I" doubles too; "step by step" style idioms are left alone). --no-auto-retakes turns this off.
- --drop removes more source-time ranges you choose (flubs, off-topic) after reading the transcript.
Writes out_dir/cut.mp4, out_dir/words_cut.json (timestamps remapped to the cut), out_dir/segments.json.
"""
import json, os, re, subprocess, sys

FILLERS = {"um", "uh", "erm", "hmm", "ah", "uhm", "umm", "mm"}
NUM = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
IDIOM_LINK = {"by", "to", "and", "after", "or", "for", "upon"}
FUNC_WORDS = {"a", "an", "the", "of", "in", "on", "at", "with", "it", "is", "this", "that", "i"}   # "step by step", "day after day" are not retakes

def norm(w):
    t = re.sub(r"[^a-z0-9$]", "", w.lower()); return NUM.get(t, t)

def find_retakes(words, window=12.0, max_len=14):
    """Restarts and repeats -> source ranges to drop (the EARLIER take; the last take is kept).
    A phrase A starting at word i is a retake when the speaker starts again at word j (same first word, within
    `window` s and 1-max_len words later) and the new take re-says most of A. Immediate doubles ("I I") too."""
    T = [norm(w["w"]) for w in words]; drops = []; i = 0
    import difflib
    while i < len(words) - 1:
        hit = None
        if T[i] and T[i] == T[i + 1]:                                                 # "the the", "and and", "4 4"
            hit = (words[i]["s"], words[i + 1]["s"])
        else:
            for j in range(i + 2, min(len(words), i + max_len + 1)):
                if T[j] != T[i] or not T[i] or words[j]["s"] - words[i]["s"] > window: continue
                if T[i + 1] in IDIOM_LINK and j == i + 2: continue                     # "section by section"
                A = T[i:j]; B = T[j:j + len(A) + 2]
                # 2-word false start only when it breaks off on a small word: "different a | different look"
                # (not lists like "my pauses, my umms" or new sentences like "I want. I give")
                short_restart = len(A) == 2 and A[1] in FUNC_WORDS
                if len(A) >= 2 and (short_restart or difflib.SequenceMatcher(None, A, B).ratio() >= 0.6):
                    hit = (words[i]["s"], words[j]["s"]); break
        if hit:
            drops.append(hit); i = next(k for k in range(i, len(words)) if words[k]["s"] >= hit[1])
        else: i += 1
    return drops

def main():
    a = sys.argv[1:]
    if len(a) < 3: print(__doc__); sys.exit(1)
    src, wj, out = a[:3]
    g = lambda k, d: a[a.index(k) + 1] if k in a else d
    gap, pad = float(g("--gap", 0.30)), float(g("--pad", 0.07))
    drops = [tuple(map(float, r.split("-"))) for r in g("--drop", "").split(",") if r.strip()]
    words = json.load(open(wj, encoding="utf-8"))
    if "--no-auto-retakes" not in a:   # restarts and repeated phrases: keep only the last take
        auto = find_retakes(words)
        for lo, hi in auto:
            said = " ".join(w["w"] for w in words if lo <= w["s"] < hi)
            print(f"  retake {lo:6.2f}-{hi:6.2f}s cut: \"{said}\"")
        drops += [(lo - 0.02, hi - 0.02) for lo, hi in auto]
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]).decode().strip())

    def dropped(w):
        t = re.sub(r"[^a-z]", "", w["w"].lower())
        if "--keep-fillers" not in a and (t in FILLERS or re.fullmatch(r"o+h+|a+h+|u+m+|u+h+|h+m+|e+r+m*|m+h*m+", t or "x")): return True
        mid = (w["s"] + w["e"]) / 2
        return any(lo <= mid <= hi for lo, hi in drops)
    keep = [w for w in words if not dropped(w)]
    if not keep: print("nothing left to keep"); sys.exit(1)

    segs, last = [], None  # merge words into spans, split where the silence between words > gap
    for w in keep:
        e = min(dur, w["e"] + pad)
        between_drop = last is not None and any(last < hi and w["s"] > lo for lo, hi in drops)
        between_cut = last is not None and any(last < x["s"] < w["s"] for x in words if dropped(x))
        if segs and w["s"] - last <= gap and not between_drop and not between_cut:
            segs[-1][1] = e
        else:
            s = max(0, w["s"] - pad)
            if segs and s < segs[-1][1]: s = segs[-1][1]
            segs.append([s, e])
        last = w["e"]
    # Whisper word spans swallow pauses ("buiiild....... section"): also cut audio silences found by
    # silencedetect, threshold = mean voice level - 2 dB (override --noise -30), unless --no-silence.
    if "--no-silence" not in a:
        vd = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
        mean = float(re.search(r"mean_volume: (-?[\d.]+)", vd).group(1))
        noise = float(g("--noise", mean - 2))
        sd = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-af", f"silencedetect=noise={noise}dB:d={gap}", "-f", "null", "-"], capture_output=True, text=True).stderr
        st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", sd)]
        en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", sd)] + [dur]
        sil = [(max(0, s0) + pad, e0 - pad) for s0, e0 in zip(st, en) if e0 - s0 > gap]
        # never let a "silence" eat a normal-length word (quiet words read as silence); only trim
        # pauses between words or inside stretched words (> 0.6 s)
        def eats(a0, b0):
            return any(x["e"] - x["s"] <= 0.6 and min(b0, x["e"]) - max(a0, x["s"]) > 0.3 * (x["e"] - x["s"]) for x in keep)
        sil = [(a0, b0) for a0, b0 in sil if not eats(a0, b0)]
        new = []
        for s0, e0 in segs:
            parts = [[s0, e0]]
            for a0, b0 in sil:
                nxt = []
                for p0, p1 in parts:
                    if b0 <= p0 or a0 >= p1: nxt.append([p0, p1])
                    else:
                        if a0 > p0: nxt.append([p0, a0])
                        if b0 < p1: nxt.append([b0, p1])
                parts = nxt
            new += parts
        print(f"  silence cut at {noise:.1f} dB: {len(sil)} pauses")
        segs = new
    segs = [s for s in segs if s[1] - s[0] > 0.12]
    kept = sum(e - s for s, e in segs)
    print(f"  {len(segs)} segments, {dur:.1f}s -> {kept:.1f}s ({100 * (1 - kept / dur):.0f}% cut)")

    # remap word times
    starts, acc = [], 0.0
    for s0, e0 in segs: starts.append(acc); acc += e0 - s0
    def tmap(t):  # source time -> cut time (clamped into the nearest kept segment)
        for (s0, e0), c in zip(segs, starts):
            if t < s0: return c
            if t <= e0: return c + t - s0
        return acc
    out_words = []
    for w in keep:
        if not any(w["s"] < e0 and w["e"] > s0 for s0, e0 in segs): continue
        ns, ne = tmap(w["s"]), tmap(w["e"])
        if ne - ns < 0.05: ne = ns + 0.05
        out_words.append({"w": w["w"], "s": round(ns, 3), "e": round(ne, 3)})
    os.makedirs(out, exist_ok=True)
    json.dump(out_words, open(os.path.join(out, "words_cut.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump([{"s": round(s, 3), "e": round(e, 3)} for s, e in segs], open(os.path.join(out, "segments.json"), "w"))
    if "--dry" in a: return

    fs = []
    for i, (s, e) in enumerate(segs):
        d = e - s
        fs.append(f"[0:v]trim={s:.3f}:{e:.3f},setpts=PTS-STARTPTS[v{i}];")
        fs.append(f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.008,afade=t=out:st={max(0, d - 0.008):.3f}:d=0.008[a{i}];")
    fs.append("".join(f"[v{i}][a{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[v][a]")
    script = os.path.join(out, "cut_filter.txt")
    open(script, "w").write("\n".join(fs))
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-nostats", "-i", src, "-/filter_complex", script, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "15", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    os.path.join(out, "cut.mp4")], check=True)
    print("  ->", os.path.join(out, "cut.mp4"))

if __name__ == "__main__":
    main()
