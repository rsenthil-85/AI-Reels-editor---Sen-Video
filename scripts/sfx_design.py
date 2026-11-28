"""sfx_design.py - automatic sound design: a sound on every visual beat, pre-mixed into ONE track.

Called by compose.py (audio pass). Density "low" = old behaviour (one whoosh per graphic);
"medium" = + item pops, ticks, count-ups, typing, card hits; "high" = + soft clicks on caption key lines
and a low thump on punch-ins (what the reference Shorts do: 7-76 hits/min, most at 40-60).
Every event = (time s, sound name, gain dB). Sounds come from assets/sfx (make_sfx.py, synthesised, MIT).
Timings mirror the animations in templates/gfx.html, so sounds land when things appear.
"""
import os, re, wave
import numpy as np

SR = 48000

def _load(path):
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        return x.reshape(-1, w.getnchannels()).mean(1)

def events(inserts, overlays, punch, words, density="high", caption_groups=None):
    ev = []
    if density == "off": return ev
    for it in inserts:
        if it.get("sfx", "auto") is None: continue
        t0, t1 = it["t0"], it["t1"]; g = it.get("gfx", {}); typ = g.get("type"); mode = it.get("mode", "top")
        if it.get("sfx") not in (None, "auto"):          # explicit choice wins
            ev.append((t0 - (0.25 if it["sfx"] == "whoosh" else 0), it["sfx"], -12)); continue
        ev.append((t0 - 0.12, "swoosh" if mode in ("top", "card") else "whoosh", -13))
        if density == "low": continue
        if mode == "card": ev.append((t0, "thump", -17))
        if g.get("step"): ev.append((t0 + 0.12, "tick", -19))
        if typ == "diagram":
            n = len([x for x in str(g.get("items", "")).split("|") if x])
            for i in range(2 * n - 1): ev.append((t0 + 0.15 + i * 0.18, "pop", -19))
            if g.get("result"): ev.append((t0 + 0.3 + (2 * n - 1) * 0.18, "pop", -16))
        elif typ == "counter":
            ev.append((t0, "countup", -18)); ev.append((t0 + min(1.4, (t1 - t0) * 0.6), "ding", -15))
        elif typ == "prompt":
            tt = t0 + 0.4
            while tt < t1 - 0.9: ev.append((tt, "typing", -21)); tt += 1.0
        elif typ == "checklist":                           # one tick per item, same timing as gfx.html
            n = len([x for x in str(g.get("items", "")).split("|") if x]); d = t1 - t0
            for i in range(n): ev.append((t0 + 0.7 + i * max(0.35, (d - 1.6) / max(1, n - 1)), "tick", -14))
            if g.get("result"): ev.append((t0 + 0.7 + (n - 1) * max(0.35, (d - 1.6) / max(1, n - 1)) + 0.3, "pop", -15))
        elif typ in ("title", "comment"):
            ev.append((t0 + 0.22, "pop", -15))
            if typ == "comment": ev.append((t0 + 1.3, "ding", -16))
        elif typ == "chapter":
            ev.append((t0 + 0.1, "thump", -15))
        elif typ == "device":                             # studio B-roll card: rows slide in
            n = len([x for x in str(g.get("rows", "")).split("|") if x])
            for i in range(n): ev.append((t0 + 0.6 + i * 0.2, "softclick", -20))
            if g.get("cursor"): ev.append((t0 + (t1 - t0) * 0.62, "click", -14))
        elif typ == "toon":                                # cartoon cut-away: a pop when its tick / tags land
            ev.append((t0 + (t1 - t0) * 0.7, "stamp", -16))
        elif typ == "endcard":
            ev.append((t0 + 0.5, "ding", -16))
    for ov in overlays:
        s = ov.get("sfx", "auto")
        if s is None: continue
        if s == "auto":
            gt = ov.get("gfx", {}).get("type")
            s = {"counter": "ding", "sticker": "pop", "bignum": "thump", "ctaword": "riser", "band": "swoosh"}.get(gt, "pop" if "pfx" in ov else "whoosh")
            if gt == "bignum": ev.append((ov["t"] - 0.15, "whoosh", -15))
            if gt == "ctaword":                           # riser into the keyword, stamp when it lands
                ev += [(ov["t"] - 0.85, "riser", -18), (ov["t"] + 0.35, "stamp", -14)]; continue
        ev.append((ov["t"] - (0.25 if s == "whoosh" else 0), s, -13))
    if density == "high":
        for p in punch or []: ev.append((p["t0"], "thump", -22))
        busy = [(it["t0"], it["t1"]) for it in inserts]
        for t in (caption_groups or []):              # soft click on each new caption line, not over graphics changes
            if not any(abs(t - a) < 0.25 for a, _ in busy): ev.append((t, "softclick", -24))
    return sorted(ev)

def render(ev, dur, sfx_dir, out_wav):
    """Mix all events into one stereo 48 kHz wav (one ffmpeg input instead of dozens)."""
    buf = np.zeros(int((dur + 2) * SR), np.float32); cache = {}
    for t, name, gdb in ev:
        if name not in cache:
            p = os.path.join(sfx_dir, name + ".wav")
            if not os.path.exists(p): continue
            cache[name] = _load(p)
        x = cache[name] * (10 ** (gdb / 20)); i = max(0, int(t * SR))
        if i >= len(buf): continue
        x = x[: len(buf) - i]; buf[i:i + len(x)] += x
    buf = np.clip(buf, -1, 1)[: int(dur * SR)]
    st = np.stack([buf, buf], 1)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())
    return len(ev)
