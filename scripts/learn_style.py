"""learn_style.py - study a reference Short/Reel the user likes, so its editing style can be added to the skill.

    python learn_style.py <youtube/instagram/tiktok url | local video file> [--out <skill>/references/refs]

Downloads the video (<= 720p) with yt-dlp, then writes into <out>/<id>/:
  contact.png  one frame per second, 10 per row (LOOK at it: layouts, cards, captions, colours)
  stats.json   title, channel, duration, views, scene-cut times, cuts per minute, average shot length, and
               audio: music bed under the voice (yes/no, dB below the voice), rough tempo, sound-effect hits
  captions.txt auto captions if available
Then Claude writes the findings into references/style-refs.md (layout mix, caption style, card types, pace)
and builds any new graphic / caption / layout pieces it needs. Downloads are for study only - never reuse
the creator's footage or graphics.
"""
import json, os, re, subprocess, sys

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    url = a[0]; here = os.path.dirname(os.path.abspath(__file__))
    base = a[a.index("--out") + 1] if "--out" in a else os.path.join(here, "..", "references", "refs")
    local = os.path.isfile(url)          # a video file on the computer (e.g. an edit the user likes)
    if local: vid = re.sub(r"[^\w-]+", "_", os.path.splitext(os.path.basename(url))[0])[:40]
    else:
        vid = re.search(r"(?:shorts/|v=|youtu\.be/|reel/|video/)([\w-]{6,})", url); vid = vid.group(1) if vid else "ref"
    d = os.path.join(base, vid); os.makedirs(d, exist_ok=True)
    if local:
        src = os.path.abspath(url)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                                   capture_output=True, text=True).stdout.strip() or 1)
        info = {"title": os.path.basename(url), "duration": dur}
    else:
        yd = [sys.executable, "-m", "yt_dlp", "-q", "--no-warnings"]
        subprocess.run(yd + ["-f", "bv*[height<=1280]+ba/b[height<=1280]/b", "--merge-output-format", "mp4", "-o", os.path.join(d, "ref.%(ext)s"),
                             "--write-info-json", url], check=True)
        subprocess.run(yd + ["--skip-download", "--write-auto-subs", "--sub-langs", "en", "--sub-format", "vtt", "-o", os.path.join(d, "ref"), url])
        src = os.path.join(d, "ref.mp4"); info = json.load(open(os.path.join(d, "ref.info.json"), encoding="utf-8"))
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-vf", "fps=1,scale=144:-1,tile=10x8", "-frames:v", "1",
                    os.path.join(d, "contact.png")], check=True)
    log = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", src, "-vf", "scale=180:-1,select='gt(scene,0.25)',showinfo",
                          "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    cuts = [round(float(x), 2) for x in re.findall(r"pts_time:([\d.]+)", log)]
    dur = float(info.get("duration") or 1)
    vtt = os.path.join(d, "ref.en.vtt"); caps = []
    if os.path.exists(vtt):
        last = ""
        for b in open(vtt, encoding="utf-8").read().split("\n\n"):
            m = re.search(r"(\d+):(\d+):([\d.]+) -->", b)
            if not m: continue
            l = [re.sub(r"<[^>]+>", "", x).strip() for x in b.split("\n")[1:] if "-->" not in x]
            l = l[-1] if l else ""
            if l and l != last: caps.append(f"[{int(m[2]) * 60 + float(m[3]):.0f}] {l}"); last = l
        open(os.path.join(d, "captions.txt"), "w", encoding="utf-8").write("\n".join(caps))
    # ---- audio: music bed under the voice, its tempo, and sound-effect hits (rough, from the mixed track)
    audio = {}
    try:
        import numpy as np, librosa
        wav = os.path.join(d, "audio.wav")
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "22050", wav], check=True)
        y, sr = librosa.load(wav, sr=22050, mono=True)
        hop = 512; rms = librosa.feature.rms(y=y, hop_length=hop)[0]; db = 20 * np.log10(rms + 1e-9)
        tt = librosa.frames_to_time(np.arange(len(db)), sr=sr, hop_length=hop)
        speech = np.zeros(len(db), bool)
        for c in caps:   # caption times ~ speech; +2.5 s each
            t0 = float(c[1:c.index("]")]); speech[(tt >= t0) & (tt < t0 + 2.5)] = True
        loud = np.percentile(db, 90)
        gaps = db[~speech] if (~speech).sum() > 20 else db[db < np.percentile(db, 25)]
        bed = float(np.median(gaps))
        audio["voice_peak_db"] = round(float(loud), 1)
        audio["between_words_db"] = round(bed, 1)
        audio["music_bed"] = "yes" if loud - bed < 26 else "no / very quiet"
        audio["music_bed_below_voice_db"] = round(float(loud - bed), 1)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        audio["tempo_bpm_rough"] = round(float(tempo[0] if hasattr(tempo, "__len__") else tempo), 0)
        # SFX hits: strong broadband onsets (whoosh/pop/ding) - peaks of high-frequency onset strength
        S_ = np.abs(librosa.stft(y, hop_length=hop)); hf = S_[int(S_.shape[0] * 0.35):]
        flux = np.maximum(0, np.diff(hf, axis=1)).sum(0); flux = flux / (flux.max() + 1e-9)
        pk = librosa.util.peak_pick(flux, pre_max=8, post_max=8, pre_avg=20, post_avg=20, delta=0.25, wait=10)
        audio["sfx_hits"] = len(pk); audio["sfx_hits_per_min"] = round(len(pk) / dur * 60, 1)
        audio["sfx_times"] = [round(float(x), 1) for x in librosa.frames_to_time(pk, sr=sr, hop_length=hop)][:40]
    except Exception as e:
        audio["error"] = str(e)[:100]
    stats = {"url": url, "audio": audio, "title": info.get("title"), "channel": info.get("channel") or info.get("uploader"),
             "duration": dur, "views": info.get("view_count"), "scene_cuts": cuts,
             "cuts_per_min": round(len(cuts) / dur * 60, 1), "avg_shot_s": round(dur / max(1, len(cuts) + 1), 1)}
    json.dump(stats, open(os.path.join(d, "stats.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps({k: stats[k] for k in ("title", "channel", "duration", "views", "cuts_per_min", "avg_shot_s")}, ensure_ascii=False))
    print("  audio:", json.dumps({k: v for k, v in audio.items() if k != "sfx_times"}))
    print("  ->", os.path.join(d, "contact.png"))

if __name__ == "__main__":
    main()
