"""screen_zoom.py - Screen tutorial style: turn a (landscape) screen recording into a vertical video that zooms to
where the action is (clicks, typing, menus opening), like FocuSee / Tella auto-zoom - free and local.

    python screen_zoom.py screen.mp4 out.mp4 [--w 1080 --h 1920] [--top 0.05] [--area 0.62] [--hold 1.6]

How: frames are sampled at 5 fps (small, grey), compared with the previous frame, and the box around what changed
is the "action". Windows of --hold seconds take the union of the action boxes; a zoom rectangle (the shape of the
target area) is fitted around it (never tighter than 38% of the screen width, never past the screen edges). A new
zoom only starts when the action moves away (overlap < 50%), so the picture does not jitter. The crop follows those
rectangles through ffmpeg sendcmd; behind it, a blurred, darkened copy of the whole screen fills the frame.
Writes out.mp4 (video only, H.264 CRF 18) and out.zoom.json (the rectangles, for the plan / FilmCraft).
"""
import json, os, subprocess, sys
import numpy as np

def probe(p):
    st = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                             "stream=width,height:format=duration", "-of", "json", p]))
    return st["streams"][0]["width"], st["streams"][0]["height"], float(st["format"]["duration"])

def main():
    a = sys.argv[1:]
    if len(a) < 2: print(__doc__); sys.exit(1)
    src, out = a[0], a[1]
    g = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d
    W, H, top, area, hold = g("--w", 1080), g("--h", 1920), g("--top", 0.05), g("--area", 0.62), g("--hold", 1.6)
    sw, sh, dur = probe(src)
    RW, RH = W, int(H * area) // 2 * 2; asp = RW / RH            # target area shape (e.g. 1080 x 1190)
    sx = 320; sy = int(sh * sx / sw) // 2 * 2; fps = 5
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vf", f"fps={fps},scale={sx}:{sy},format=gray", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, sy, sx).astype(np.int16)
    boxes = []                                                   # (t, x0, y0, x1, y1) in source pixels, or None
    for i in range(1, len(fr)):
        d = np.abs(fr[i] - fr[i - 1]) > 18
        if d.sum() < sx * sy * 0.0008: boxes.append((i / fps, None)); continue
        ys, xs = np.nonzero(d)
        x0, x1 = np.percentile(xs, 2), np.percentile(xs, 98); y0, y1 = np.percentile(ys, 2), np.percentile(ys, 98)
        k = sw / sx; boxes.append((i / fps, (x0 * k, y0 * k, x1 * k, y1 * k)))

    def fit(bx):   # zoom rectangle of the target shape around a box, inside the screen
        if bx is None: return None
        x0, y0, x1, y1 = bx; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w = max(x1 - x0, (y1 - y0) * asp, sw * 0.38) * 1.25; h = w / asp
        if w > sw: w = sw; h = w / asp
        if h > sh: h = sh; w = h * asp
        x = min(max(cx - w / 2, 0), sw - w); y = min(max(cy - h / 2, 0), sh - h)
        return [int(x) // 2 * 2, int(y) // 2 * 2, int(w) // 2 * 2, int(h) // 2 * 2]
    full = fit((0, 0, sw, sh))                                    # the whole screen at the target shape (letterboxed if needed)
    if full[2] < sw * 0.98: full = [0, max(0, int((sh - sw / asp) / 2)) // 2 * 2, sw // 2 * 2, int(min(sh, sw / asp)) // 2 * 2]
    def iou(a_, b_):
        ax1, ay1, bx1, by1 = a_[0] + a_[2], a_[1] + a_[3], b_[0] + b_[2], b_[1] + b_[3]
        iw = max(0, min(ax1, bx1) - max(a_[0], b_[0])); ih = max(0, min(ay1, by1) - max(a_[1], b_[1]))
        inter = iw * ih; return inter / (a_[2] * a_[3] + b_[2] * b_[3] - inter + 1e-9)
    segs = [[0.0, full]]; t = 1.0                                 # first second: the whole screen
    while t < dur:
        win = [b for (tt, b) in boxes if t <= tt < t + hold and b is not None]
        if win:
            u = (min(b[0] for b in win), min(b[1] for b in win), max(b[2] for b in win), max(b[3] for b in win))
            r = fit(u)
            if r[2] > sw * 0.8: r = full                          # action all over the screen: show it all
            if iou(r, segs[-1][1]) < 0.5: segs.append([t, r])
        t += hold
    cmd = "".join(f"{s:.2f} crop@z w {r[2]}, crop@z h {r[3]}, crop@z x {r[0]}, crop@z y {r[1]};\n" for s, r in segs)
    cf = out + ".cmd"; open(cf, "w").write(cmd)
    y0 = int(H * top) // 2 * 2
    fg = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.25[bg];"
          f"[b]sendcmd=f='{os.path.basename(cf)}',crop@z=w={full[2]}:h={full[3]}:x={full[0]}:y={full[1]},scale={RW}:{RH},"
          f"pad={RW}:{RH}:(ow-iw)/2:(oh-ih)/2:color=black[z];[bg][z]overlay=0:{y0},fps=30,format=yuv420p")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", os.path.abspath(src), "-vf" if False else "-filter_complex", fg,
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", os.path.abspath(out)], check=True,
                   cwd=os.path.dirname(os.path.abspath(cf)))
    json.dump({"screen": [sw, sh], "segments": [{"t": s, "rect": r} for s, r in segs]}, open(out + ".zoom.json", "w"), indent=1)
    print(f"  {len(segs)} zoom steps over {dur:.0f} s -> {out}")

if __name__ == "__main__":
    main()
