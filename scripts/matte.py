"""matte.py - protection mattes for the background swap on walls that are close to skin colour.

    python matte.py <video> <out_dir> [--w 1080 --h 1920 --fx 0.5 --fy 0.45] [--n 6]
    python matte.py <video> <out_dir> --every 1.0      # moving matte: one AI frame per second -> core.mp4 / outer.mp4
                                                        # (~11 s per AI frame: a 60 s video takes ~11 min)

The MIT BiRefNet-lite model (assets/models/birefnet_lite.onnx) cuts the person out of only --n frames
(~11 s each on a laptop CPU), then:
  core.png  = where the person is in EVERY sampled frame, shrunk a little  -> always kept (no holes in the face)
  outer.png = where the person is in ANY sampled frame, grown generously   -> outside is always background
compose.py keys the band between them with ffmpeg's colour key. Frames go through the same scale/crop as a
reel in compose.py, so the mattes line up. Works when the camera is still (tripod / propped phone).
"""
import io, json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "..", "assets", "models", "birefnet_lite.onnx")

def frames(src, n, W, H, fx, fy):
    d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]).decode())
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}:'(iw-{W})*{fx}':'(ih-{H})*{max(0, min(1, fy - 0.1))}'")
    for i in range(n):
        t = d * (i + 0.5) / n
        png = subprocess.check_output(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf", vf,
                                       "-f", "image2pipe", "-c:v", "png", "-"])
        yield Image.open(io.BytesIO(png)).convert("RGB")

def moving(src, out, W, H, fx, fy, every, sess):
    """One mask per `every` seconds; core/outer per keyframe, blended to 30 fps videos that follow the speaker."""
    from scipy.ndimage import binary_fill_holes
    d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]).decode())
    n = max(2, int(d / every) + 1)
    tmp = os.path.join(out, "_kf"); os.makedirs(tmp, exist_ok=True)
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}:'(iw-{W})*{fx}':'(ih-{H})*{max(0, min(1, fy - 0.1))}'")
    for i in range(n):
        t = min(d - 0.05, i * every)
        png = subprocess.check_output(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf", vf,
                                       "-f", "image2pipe", "-c:v", "png", "-"])
        im = Image.open(io.BytesIO(png)).convert("RGB")
        x = np.asarray(im.resize((1024, 1024), Image.BILINEAR)).astype(np.float32) / 255
        x = ((x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]).transpose(2, 0, 1)[None].astype(np.float32)
        y = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
        m = np.asarray(Image.fromarray((255 / (1 + np.exp(-y))).astype(np.uint8)).resize((W, H), Image.BILINEAR)) > 127
        core = Image.fromarray((binary_fill_holes(m) * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(13)).filter(ImageFilter.GaussianBlur(3))
        outer = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(31)).filter(ImageFilter.GaussianBlur(6))
        core.save(os.path.join(tmp, f"c_{i:04d}.png")); outer.save(os.path.join(tmp, f"o_{i:04d}.png"))
        print(f"  keyframe {i + 1}/{n}", flush=True)
    for kind in ("c", "o"):   # keyframes at 1/every fps -> 30 fps with cross-blending between them
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-framerate", f"{1 / every:.4f}", "-i", os.path.join(tmp, f"{kind}_%04d.png"),
                        "-vf", "framerate=fps=30:interp_start=0:interp_end=255:scene=100,format=gray", "-c:v", "libx264", "-crf", "12",
                        "-pix_fmt", "yuv420p", os.path.join(out, ("core" if kind == "c" else "outer") + ".mp4")], check=True)
    json.dump({"every": every, "n": n, "w": W, "h": H, "fx": fx, "fy": fy}, open(os.path.join(out, "matte.json"), "w"))
    print("  ->", os.path.join(out, "core.mp4"), os.path.join(out, "outer.mp4"))

def main():
    a = sys.argv[1:]
    if len(a) < 2: print(__doc__); sys.exit(1)
    g = lambda k, dflt: a[a.index(k) + 1] if k in a else dflt
    src, out = a[0], a[1]; os.makedirs(out, exist_ok=True)
    W, H = int(g("--w", 1080)), int(g("--h", 1920)); fx, fy = float(g("--fx", 0.5)), float(g("--fy", 0.45)); n = int(g("--n", 6))
    if not os.path.exists(MODEL):
        print("missing assets/models/birefnet_lite.onnx (install.ps1 -WithMatte)"); sys.exit(1)
    import onnxruntime as ort
    so = ort.SessionOptions(); so.intra_op_num_threads = os.cpu_count() or 4
    sess = ort.InferenceSession(MODEL, so, providers=["CPUExecutionProvider"])
    if "--every" in a:
        return moving(src, out, W, H, fx, fy, float(g("--every", 1.0)), sess)
    masks = []
    for i, im in enumerate(frames(src, n, W, H, fx, fy)):
        x = np.asarray(im.resize((1024, 1024), Image.BILINEAR)).astype(np.float32) / 255
        x = ((x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]).transpose(2, 0, 1)[None].astype(np.float32)
        y = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
        m = Image.fromarray((255 / (1 + np.exp(-y))).astype(np.uint8)).resize((W, H), Image.BILINEAR)
        masks.append(np.asarray(m).astype(np.float32) / 255); print(f"  frame {i + 1}/{n}", flush=True)
    M = np.stack(masks)
    from scipy.ndimage import binary_fill_holes                       # shirt prints / logos can drop out of one mask
    core = Image.fromarray((binary_fill_holes(M.min(0) > 0.5) * 255).astype(np.uint8))
    core = core.filter(ImageFilter.MinFilter(int(g("--erode", 21)))).filter(ImageFilter.GaussianBlur(4))     # shrink, soften
    outer = Image.fromarray(((M.max(0) > 0.25) * 255).astype(np.uint8))
    outer = outer.filter(ImageFilter.MaxFilter(int(g("--grow", 41)))).filter(ImageFilter.GaussianBlur(8))   # grow, soften
    core.save(os.path.join(out, "core.png")); outer.save(os.path.join(out, "outer.png"))
    json.dump({"n": n, "w": W, "h": H, "fx": fx, "fy": fy}, open(os.path.join(out, "matte.json"), "w"))
    print("  ->", os.path.join(out, "core.png"), os.path.join(out, "outer.png"))

if __name__ == "__main__":
    main()
