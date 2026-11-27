"""audio_meter.py - the same rough sound meter learn_style.py uses on references, for our own renders.

    python audio_meter.py video.mp4 [words.json]

Prints voice peak, level between words (music + effects), music bed below voice (dB), sound-effect hits/min.
Compare with the numbers in references/style-refs.md (refs: bed ~3-6 dB under the voice peaks, 7-76 hits/min).
"""
import json, os, subprocess, sys, tempfile
import numpy as np

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    import librosa
    wav = os.path.join(tempfile.gettempdir(), "pve_meter.wav")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", a[0], "-vn", "-ac", "1", "-ar", "22050", wav], check=True)
    y, sr = librosa.load(wav, sr=22050, mono=True); dur = len(y) / sr
    hop = 512; db = 20 * np.log10(librosa.feature.rms(y=y, hop_length=hop)[0] + 1e-9)
    tt = librosa.frames_to_time(np.arange(len(db)), sr=sr, hop_length=hop)
    speech = np.zeros(len(db), bool)
    if len(a) > 1:
        for w in json.load(open(a[1], encoding="utf-8")): speech[(tt >= w["s"]) & (tt < w["e"])] = True
    loud = np.percentile(db, 90); gaps = db[~speech] if (~speech).sum() > 20 else db[db < np.percentile(db, 25)]
    S = np.abs(librosa.stft(y, hop_length=hop)); hf = S[int(S.shape[0] * 0.35):]
    flux = np.maximum(0, np.diff(hf, axis=1)).sum(0); flux = flux / (flux.max() + 1e-9)
    pk = librosa.util.peak_pick(flux, pre_max=8, post_max=8, pre_avg=20, post_avg=20, delta=0.25, wait=10)
    print(json.dumps({"voice_peak_db": round(float(loud), 1), "between_words_db": round(float(np.median(gaps)), 1),
                      "music_bed_below_voice_db": round(float(loud - np.median(gaps)), 1),
                      "sfx_hits_per_min": round(len(pk) / dur * 60, 1)}))

if __name__ == "__main__":
    main()
