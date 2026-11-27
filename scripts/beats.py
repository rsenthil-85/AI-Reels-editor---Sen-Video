"""beats.py - beat and bar times of a music file (librosa, ISC licence), for cutting on the beat.

    python beats.py song.mp3 [--out song.beats.json]

Writes {"bpm", "beats": [...], "bars": [...], "onsets": [...]} - same shape as music.py's .beats.json,
so montage.py and compose.py's "snap" work with your own tracks too.
"""
import json, os, sys

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    import librosa
    y, sr = librosa.load(a[0], sr=22050, mono=True)
    tempo, frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    beats = librosa.frames_to_time(frames, sr=sr).round(3).tolist()
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time").round(3).tolist()
    # downbeats: pick the phase (0-3) whose beats carry the most onset energy
    env = librosa.onset.onset_strength(y=y, sr=sr)
    best = max(range(4), key=lambda p: sum(env[f] for f in frames[p::4] if f < len(env)))
    bars = beats[best::4]
    bpm = float(tempo[0] if hasattr(tempo, "__len__") else tempo)
    out = a[a.index("--out") + 1] if "--out" in a else os.path.splitext(a[0])[0] + ".beats.json"
    json.dump({"bpm": round(bpm, 2), "beats": beats, "bars": bars, "onsets": onsets}, open(out, "w"))
    print(f"  {bpm:.1f} bpm, {len(beats)} beats, {len(bars)} bars -> {out}")

if __name__ == "__main__":
    main()
