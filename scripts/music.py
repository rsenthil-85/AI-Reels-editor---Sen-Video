"""music.py - original royalty-free background music, synthesised in numpy (no samples, no licences).

    python music.py out.wav --seconds 70 --mood lofi [--bpm 80] [--seed 7]
    moods: lofi, upbeat, corporate, cinematic, chill, tech

Writes out.wav (48 kHz stereo) and out.beats.json {"bpm", "beats": [...], "bars": [...]} so cuts can land on the beat.
The track ends on a resolved chord at --seconds. Keep it under the voice (compose.py ducks it).
"""
import json, math, sys, wave
import numpy as np

SR = 48000
MOODS = {  # bpm, scale intervals, progression (scale degrees), sound set
    "lofi":      dict(bpm=78,  scale=[0, 2, 3, 5, 7, 9, 10], prog=[0, 3, 6, 2], keys="ep", drums="lofi", swing=0.12),
    "chill":     dict(bpm=86,  scale=[0, 2, 4, 5, 7, 9, 11], prog=[0, 5, 3, 4], keys="ep", drums="soft", swing=0.06),
    "upbeat":    dict(bpm=116, scale=[0, 2, 4, 5, 7, 9, 11], prog=[0, 4, 5, 3], keys="pluck", drums="pop", swing=0.0),
    "corporate": dict(bpm=104, scale=[0, 2, 4, 5, 7, 9, 11], prog=[5, 3, 0, 4], keys="pluck", drums="soft", swing=0.0),
    "tech":      dict(bpm=120, scale=[0, 2, 3, 5, 7, 8, 10], prog=[0, 5, 2, 6], keys="saw", drums="pop", swing=0.0),
    "cinematic": dict(bpm=72,  scale=[0, 2, 3, 5, 7, 8, 10], prog=[0, 5, 2, 6], keys="pad", drums="none", swing=0.0),
}

def hz(m): return 440.0 * 2 ** ((m - 69) / 12)

def env(n, a=0.01, d=0.3, s=0.6, r=0.2):
    t = np.arange(n) / SR; L = n / SR
    e = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / max(d, 1e-3)))
    rel = np.clip((L - t) / max(r, 1e-3), 0, 1)
    return e * rel

def lp(x, cut):  # one-pole low-pass
    k = 1 - math.exp(-2 * math.pi * cut / SR); y = np.empty_like(x); acc = 0.0
    for i in range(len(x)): acc += k * (x[i] - acc); y[i] = acc
    return y

def tone(kind, f, dur, vel=0.5, rng=None):
    n = int(dur * SR); t = np.arange(n) / SR
    if kind == "ep":      # FM electric piano
        x = np.sin(2 * np.pi * f * t + 1.2 * np.exp(-t * 6) * np.sin(2 * np.pi * f * 2 * t)) * env(n, 0.005, 0.6, 0.25, 0.25)
    elif kind == "pluck":
        x = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * env(n, 0.003, 0.18, 0.05, 0.1)
    elif kind == "saw":
        ph = (f * t) % 1; x = (2 * ph - 1) * env(n, 0.01, 0.25, 0.3, 0.15); x = lp(x, 2400)
    elif kind == "pad":
        x = sum(np.sin(2 * np.pi * f * (1 + d) * t) for d in (-0.003, 0, 0.004)) / 3 * env(n, 0.6, 1.0, 0.8, 0.8)
    elif kind == "bass":
        x = (np.sin(2 * np.pi * f * t) + 0.2 * np.sin(4 * np.pi * f * t)) * env(n, 0.005, 0.3, 0.6, 0.08)
    else: x = np.zeros(n)
    return x * vel

def drum(kind, rng):
    if kind == "kick":
        n = int(0.35 * SR); t = np.arange(n) / SR
        return np.sin(2 * np.pi * np.cumsum(50 + 110 * np.exp(-t * 30)) / SR) * np.exp(-t * 9)
    if kind == "snare":
        n = int(0.22 * SR); t = np.arange(n) / SR
        return (0.6 * rng.standard_normal(n) * np.exp(-t * 18) + 0.4 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)) * 0.7
    if kind == "hat":
        n = int(0.06 * SR); x = rng.standard_normal(n); x = x - lp(x, 6000)
        return x * np.exp(-np.arange(n) / SR * 60) * 0.35
    return np.zeros(1)

def add(buf, x, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= buf.shape[0]: return
    x = x[: buf.shape[0] - i]
    buf[i:i + len(x), 0] += x * gain * (1 - max(0, pan)); buf[i:i + len(x), 1] += x * gain * (1 + min(0, pan))

def compose(seconds, mood="lofi", bpm=None, seed=7):
    M = MOODS[mood]; rng = np.random.default_rng(seed)
    bpm = bpm or M["bpm"]; beat = 60 / bpm; bar = 4 * beat
    n_bars = max(2, round(seconds / bar)); bar = seconds / n_bars; beat = bar / 4; bpm = 60 / beat  # bars fit exactly
    root = 57 + int(rng.integers(0, 5)); sc = M["scale"]
    buf = np.zeros((int((seconds + 2) * SR), 2))
    beats, bars = [], []
    for b in range(n_bars):
        t0 = b * bar; bars.append(round(t0, 3))
        deg = M["prog"][b % len(M["prog"])] if b < n_bars - 1 else 0
        chord = [root + sc[(deg + k) % 7] + 12 * ((deg + k) // 7) for k in (0, 2, 4, 6)]
        last = b == n_bars - 1
        # harmony
        if M["keys"] == "pad" or mood in ("lofi", "chill", "cinematic"):
            for m in chord[:3]: add(buf, tone("pad", hz(m), bar + 0.6, 0.10), t0, pan=rng.uniform(-.3, .3))
        if M["keys"] in ("ep", "pluck", "saw") and not last:
            pattern = [0, 1.5, 2, 3] if M["keys"] == "ep" else [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5]
            for i, p in enumerate(pattern):
                m = chord[i % len(chord)] + (12 if M["keys"] == "pluck" else 0)
                sw = M["swing"] * beat if (p % 1) else 0
                add(buf, tone(M["keys"], hz(m), beat * 1.4, 0.13 if M["keys"] != "saw" else 0.07), t0 + p * beat + sw, pan=rng.uniform(-.4, .4))
        if last:
            for m in chord: add(buf, tone("ep" if M["keys"] != "pad" else "pad", hz(m), bar * 1.5, 0.12), t0)
        # bass
        bnotes = [0, 2.5] if mood in ("lofi", "chill", "cinematic") else [0, 1, 2, 3]
        for p in bnotes:
            if last and p > 0: break
            add(buf, tone("bass", hz(chord[0] - 24), beat * (1.5 if len(bnotes) == 2 else 0.9), 0.32), t0 + p * beat)
        # drums
        dk = M["drums"]
        for q in range(4):
            tb = t0 + q * beat; beats.append(round(tb, 3))
            if dk == "none" or last: continue
            if q in (0, 2) or (dk == "pop" and q in (1, 3) and False): add(buf, drum("kick", rng), tb, 0.55 if dk != "soft" else 0.35)
            if q in (1, 3) and dk in ("lofi", "pop"): add(buf, drum("snare", rng), tb + (M["swing"] * beat * 0.3), 0.30)
            if dk in ("lofi", "pop", "soft"):
                for h in (0, 0.5): add(buf, drum("hat", rng), tb + h * beat + (M["swing"] * beat if h else 0), 0.25 if dk != "soft" else 0.15, pan=0.2)
    # lofi warmth: low-pass + gentle saturation; master to -1 dBFS peak
    if mood in ("lofi", "chill"):
        for c in range(2): buf[:, c] = lp(buf[:, c], 5000)
    buf = np.tanh(buf * 1.4) / 1.4
    n_end = int((seconds + 1.2) * SR); buf = buf[:n_end]
    fade = int(1.0 * SR); buf[-fade:] *= np.linspace(1, 0, fade)[:, None]
    buf /= (np.abs(buf).max() + 1e-9); buf *= 0.89
    return buf, {"bpm": round(bpm, 2), "beats": beats, "bars": bars, "mood": mood}

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    g = lambda k, d: a[a.index(k) + 1] if k in a else d
    out = a[0]
    buf, info = compose(float(g("--seconds", 60)), g("--mood", "lofi"), float(g("--bpm", 0)) or None, int(g("--seed", 7)))
    with wave.open(out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((buf * 32767).astype(np.int16).tobytes())
    json.dump(info, open(out.rsplit(".", 1)[0] + ".beats.json", "w"))
    print(f"  {out}: {info['mood']} {info['bpm']} bpm, {len(info['bars'])} bars")

if __name__ == "__main__":
    main()
