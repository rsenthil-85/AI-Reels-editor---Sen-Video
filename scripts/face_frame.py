"""face_frame.py - find where the speaker's face is, so split-screen reels frame it right (auto face framing).

    python face_frame.py <video> <out_dir> [--n 3] [--w 1080 --h 1920]

Cuts the person out of --n frames with the MIT BiRefNet-lite model (assets/models/birefnet_lite.onnx,
~11 s per frame on a laptop CPU), finds the head (top of the person down to where the shoulders widen),
and writes <out_dir>/face.json: {"face_x", "face_y", "head_top", "frames", "method"} as fractions of the
reel frame. compose.py centres the bottom panel and the zoom-ins on face_y.
Runs in the background during the intake questions (autoedit.py --analyze starts it), so it adds no wait.
Without the model it writes method "default" (0.5 / 0.45) and the plan keeps the old fixed framing.
"""
import io, json, os, subprocess, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "..", "assets", "models", "birefnet_lite.onnx")

def frames(src, n, W, H):
    d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]).decode())
    for i in range(n):
        t = d * (i + 1) / (n + 1)
        png = subprocess.check_output(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1",
                                       "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", "-f", "image2pipe", "-c:v", "png", "-"])
        yield Image.open(io.BytesIO(png)).convert("RGB")

def head_box(mask):
    """mask: HxW bool person mask -> (top, face_cy, face_cx) in pixels, or None."""
    H, W = mask.shape
    rows = mask.sum(1)
    on = np.where(rows > 0.03 * W)[0]
    if len(on) == 0: return None
    top = int(on[0])
    # head width = median width in the first 12% of the frame height below the top of the head
    band = rows[top: top + int(0.12 * H)]
    hw = float(np.median(band)) if len(band) else 0
    if hw <= 0: return None
    # shoulders: first row below the head where the person is > 1.7x the head width
    below = np.where(rows[top + int(0.05 * H):] > 1.7 * hw)[0]
    chin = top + int(0.05 * H) + int(below[0]) if len(below) else min(H - 1, top + int(1.3 * hw))
    chin = min(chin, top + int(1.6 * hw))                      # a head is never much taller than ~1.5x its width
    cy = top + 0.55 * (chin - top)                             # eyes/nose sit a little below the middle of the head
    cols = np.where(mask[top:chin].any(0))[0]
    cx = float(cols.mean()) if len(cols) else W / 2
    return top, cy, cx

def main():
    a = sys.argv[1:]
    if len(a) < 2: print(__doc__); sys.exit(1)
    g = lambda k, d: a[a.index(k) + 1] if k in a else d
    src, out = a[0], a[1]; os.makedirs(out, exist_ok=True)
    W, H, n = int(g("--w", 1080)), int(g("--h", 1920)), int(g("--n", 3))
    res = {"face_x": 0.5, "face_y": 0.45, "head_top": None, "frames": 0, "method": "default"}
    if os.path.exists(MODEL):
        import onnxruntime as ort
        so = ort.SessionOptions(); so.intra_op_num_threads = max(1, (os.cpu_count() or 4) // 2)   # leave CPU for the user's other work
        sess = ort.InferenceSession(MODEL, so, providers=["CPUExecutionProvider"])
        found = []
        for im in frames(src, n, W, H):
            x = np.asarray(im.resize((1024, 1024), Image.BILINEAR)).astype(np.float32) / 255
            x = ((x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]).transpose(2, 0, 1)[None].astype(np.float32)
            y = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
            m = np.asarray(Image.fromarray((255 / (1 + np.exp(-y))).astype(np.uint8)).resize((W, H), Image.BILINEAR)) > 127
            hb = head_box(m)
            if hb: found.append(hb)
        if found:
            top, cy, cx = np.median(np.array(found), axis=0)
            res = {"face_x": round(float(cx) / W, 3), "face_y": round(float(cy) / H, 3), "head_top": round(float(top) / H, 3),
                   "frames": len(found), "method": "birefnet"}
    json.dump(res, open(os.path.join(out, "face.json"), "w"), indent=1)
    print(json.dumps(res))

if __name__ == "__main__":
    main()
