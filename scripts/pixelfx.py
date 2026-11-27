"""pixelfx.py - export a pixelfx effect (vendor/pixelfx, MIT) as a transparent .mov overlay.

    python pixelfx.py ui/confetti out.mov [--width 600] [--fps 30] [--palette '["#fff","#E8603C"]']

Lists effects: node vendor/pixelfx/tools/list.mjs. Good for video: ui/confetti, explosions/firework-burst,
spawn/coin-drop, pickups/collect-burst, arcane/star-fall, holy/sunburst, sci-fi/glitch, transitions/glitch-wipe.
Pixels are scaled with nearest-neighbour so the pixel-art look stays crisp. Use in plan.json overlays:
{"t": 48, "pfx": "ui/confetti", "x": 0.5, "y": 0.3, "w": 700}
"""
import glob, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PFX = os.path.join(HERE, "..", "vendor", "pixelfx")

def export(fx_id, out, width=600, fps=30, palette=None):
    tmp = tempfile.mkdtemp(prefix="pfx_")
    cmd = ["node", os.path.join(PFX, "tools", "render.mjs"), fx_id, "--sheet", "--no-actor", "--bg", "none", "--out", tmp]
    if palette: cmd += ["--opts", json.dumps({"palette": palette})]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    js = glob.glob(os.path.join(tmp, "**", "*.json"), recursive=True)[0]; png = js[:-5] + ".png"
    meta = json.load(open(js)); fr = meta["frames"]; n = len(fr); fw, fh = fr[0]["frame"]["w"], fr[0]["frame"]["h"]
    probe = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", png]).decode().split(",")
    cols, rows = int(probe[0]) // fw, int(probe[1]) // fh
    src_fps = round(1000 / (fr[0].get("duration") or 33))
    w = int(width) // 2 * 2; h = int(round(fh * w / fw)) // 2 * 2
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", png, "-vf",
                    f"untile={cols}x{rows},setpts=N/{src_fps}/TB,trim=end_frame={n},fps={fps},scale={w}:{h}:flags=neighbor,format=argb",
                    "-c:v", "qtrle", out], check=True)
    return out, n / src_fps, (w, h)

if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2: print(__doc__); sys.exit(1)
    g = lambda k, d: a[a.index(k) + 1] if k in a else d
    o, d, size = export(a[0], a[1], int(g("--width", 600)), int(g("--fps", 30)), json.loads(g("--palette", "null")))
    print(f"  {a[0]} -> {o} ({d:.2f}s, {size[0]}x{size[1]})")
