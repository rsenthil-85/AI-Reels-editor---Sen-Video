"""montage.py - cut B-roll clips to the music: one shot per bar (or every N beats), with slow push-ins.

    python montage.py clips_dir music.wav out.mp4 [--every bar|2beats|beat] [--w 1920 --h 1080] [--seconds 30]

The music needs a .beats.json next to it (music.py writes one; for your own track run beats.py first).
Each clip contributes its most active stretch (highest scene/motion score). Clips are used in name order and
loop if there are fewer clips than shots. Audio = the music only (mastered to -14 LUFS).
"""
import glob, json, os, subprocess, sys

def main():
    a = sys.argv[1:]
    if len(a) < 3: print(__doc__); sys.exit(1)
    g = lambda k, d: a[a.index(k) + 1] if k in a else d
    clips = sorted(sum([glob.glob(os.path.join(a[0], e)) for e in ("*.mp4", "*.mov", "*.MP4", "*.MOV", "*.mkv")], []))
    if not clips: print("no clips"); sys.exit(1)
    music, out = a[1], a[2]; W, H = int(g("--w", 1920)), int(g("--h", 1080))
    bj = os.path.splitext(music)[0] + ".beats.json"
    if not os.path.exists(bj): print(f"missing {bj}: run beats.py on the music first"); sys.exit(1)
    B = json.load(open(bj)); every = g("--every", "bar")
    marks = B["bars"] if every == "bar" else B["beats"][::2] if every == "2beats" else B["beats"]
    total = float(g("--seconds", 0)) or (marks[-1] if marks else 30)
    marks = [m for m in marks if m < total] + [total]
    if marks[0] > 0.05: marks = [0.0] + marks
    parts, fl = [], []
    for i, (t0, t1) in enumerate(zip(marks, marks[1:])):
        d = t1 - t0; c = clips[i % len(clips)]
        cd = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", c]).decode())
        ss = max(0.0, min(cd - d, cd * 0.3))  # skip shaky starts; take from ~30% in
        parts += ["-ss", f"{ss:.2f}", "-t", f"{d + 0.05:.3f}", "-i", c]
        z = "1+0.04*on/({:d})".format(max(1, int(d * 30)))
        fl.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,"
                  f"zoompan=z='{z}':d=1:s={W}x{H}:fps=30,trim=0:{d:.3f},setpts=PTS-STARTPTS[v{i}]")
    n = len(marks) - 1
    fl.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,eq=contrast=1.06:saturation=1.05[v]")
    fl.append(f"[{n}:a]atrim=0:{total:.3f},afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5,loudnorm=I=-14:TP=-1.5[a]")
    script = out + ".filter.txt"; open(script, "w").write(";\n".join(fl))
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error"] + parts + ["-i", music, "-/filter_complex", script, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "faster", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", out], check=True)
    os.remove(script); print(f"  {n} shots on the {every} -> {out}")

if __name__ == "__main__":
    main()
