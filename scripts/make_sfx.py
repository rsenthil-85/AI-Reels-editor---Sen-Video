"""make_sfx.py - synthesize the house SFX pack (no downloads, no licences): whoosh, pop, ding, click, riser.

    python make_sfx.py out_dir
"""
import os, sys, wave
import numpy as np

SR = 48000
rng = np.random.default_rng(7)

def env(n, a, d):
    t = np.linspace(0, 1, n); return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(d, 1e-4))

def lowpass(x, k):
    y = np.zeros_like(x); acc = 0.0
    for i, v in enumerate(x): acc += k[i] * (v - acc); y[i] = acc
    return y

def save(path, x, gain=0.8):
    x = x / (np.max(np.abs(x)) + 1e-9) * gain
    st = np.stack([x, x], 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())

def whoosh(d=0.55):
    n = int(SR * d); t = np.linspace(0, 1, n)
    k = 0.02 + 0.25 * np.sin(np.pi * t) ** 2          # filter opens then closes
    x = lowpass(rng.standard_normal(n), k)
    return x * np.sin(np.pi * t) ** 1.5

def pop(d=0.09):
    n = int(SR * d); t = np.arange(n) / SR
    f = 900 * np.exp(-t * 40) + 250
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.02, 0.18)

def ding(d=0.9):
    n = int(SR * d); t = np.arange(n) / SR
    x = sum(a * np.sin(2 * np.pi * f * t) for f, a in [(1568, 1), (2350, .45), (3136, .25), (4700, .1)])
    return x * env(n, 0.003, 0.35)

def click(d=0.03):
    n = int(SR * d); return rng.standard_normal(n) * env(n, 0.01, 0.12) * 0.7

def riser(d=1.2):
    n = int(SR * d); t = np.linspace(0, 1, n)
    x = lowpass(rng.standard_normal(n), 0.01 + 0.3 * t ** 2) + 0.3 * np.sin(2 * np.pi * np.cumsum(200 + 900 * t ** 2) / SR)
    return x * t ** 2 * (1 - np.clip((t - .95) / .05, 0, 1))

def tick(d=0.05):        # UI tick: short bright tone + click (checklist items, step dots, count steps)
    n = int(SR * d); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 2400 * t) * 0.6 + rng.standard_normal(n) * 0.25) * env(n, 0.002, 0.08)

def softclick(d=0.04):   # very soft mouse-click for caption beats (sits under the voice)
    n = int(SR * d); t = np.arange(n) / SR
    x = rng.standard_normal(n); x = x - lowpass(x, np.full(n, 0.15))          # high-passed noise
    return (x * 0.5 + np.sin(2 * np.pi * 1300 * t) * 0.4) * env(n, 0.001, 0.05)

def swoosh(d=0.28):      # short fast swoosh for card changes
    n = int(SR * d); t = np.linspace(0, 1, n)
    x = lowpass(rng.standard_normal(n), 0.05 + 0.5 * np.sin(np.pi * t) ** 3)
    return x * np.sin(np.pi * t) ** 2

def thump(d=0.35):       # low punch under zoom-ins / full-screen card hits
    n = int(SR * d); t = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(45 + 120 * np.exp(-t * 25)) / SR) * env(n, 0.003, 0.25)

def typing(d=1.0):       # keyboard: irregular soft key clicks (prompt boxes typing)
    n = int(SR * d); x = np.zeros(n)
    t = 0.0
    while t < d - 0.05:
        i = int(t * SR); k = click(0.025) * rng.uniform(0.4, 1.0)
        x[i:i + len(k)] += k[: n - i]; t += rng.uniform(0.06, 0.13)
    return x

def countup(d=1.2, steps=10):   # rising ticks for a number counting up
    n = int(SR * d); x = np.zeros(n)
    for j in range(steps):
        i = int(d * (j / steps) ** 0.8 * SR); tt = np.arange(int(0.04 * SR)) / SR
        k = np.sin(2 * np.pi * (900 + 90 * j) * tt) * env(len(tt), 0.002, 0.15)
        x[i:i + len(k)] += k[: n - i] * (0.5 + 0.5 * j / steps)
    return x

def stamp(d=0.4):        # stamp / hit for badges and stamps
    return thump(d) * 0.8 + np.concatenate([click(0.03) * 2, np.zeros(int(SR * d) - int(SR * 0.03))])

PACK = [("whoosh", whoosh, .7), ("pop", pop, .6), ("ding", ding, .55), ("click", click, .5), ("riser", riser, .6),
        ("tick", tick, .5), ("softclick", softclick, .45), ("swoosh", swoosh, .6), ("thump", thump, .8),
        ("typing", typing, .5), ("countup", countup, .5), ("stamp", stamp, .8)]

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    for name, fn, g in PACK:
        save(os.path.join(out, name + ".wav"), fn(), g); print(" ", name)
