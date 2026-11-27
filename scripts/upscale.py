"""upscale.py - AI-upscale a low-res video (WhatsApp / phone exports) with Real-ESRGAN general-x4v3, CPU.

    python upscale.py in.mp4 out.mp4 --w 1080 --h 1920 [--half] [--threads 8] [--test]

--half feeds the model half-size frames (4x of half = ~2x): ~4x faster, nearly as sharp on soft phone video.
Uses OpenVINO on the CPU when available (2x faster than torch). Intel iGPU (GPU plugin) gives WRONG output
for this model on UHD 620 - never use it. Speed on i7-8665U: 576x1024 full 8.7 s/frame, --half 2.4 s/frame.

Runs in any Python with torch (e.g. E:/ltx/venv). Model: realesr-general-x4v3.pth (SRVGGNetCompact, BSD-3).
--denoise (0..1) blends the model's denoising (wdn) weights: 0 = keep grain/detail, 1 = strongest clean-up.
Audio is copied untouched. Frames are piped: no temp images on disk.
"""
import os, subprocess, sys, time
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

MODEL = os.environ.get("ESRGAN_MODEL", r"E:\senvideo-test\models\upscale\realesr-general-x4v3.pth")

class SRVGGNetCompact(nn.Module):
    def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4):
        super().__init__()
        self.upscale = upscale
        self.body = nn.ModuleList([nn.Conv2d(num_in_ch, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)])
        for _ in range(num_conv):
            self.body.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1)); self.body.append(nn.PReLU(num_parameters=num_feat))
        self.body.append(nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1))
        self.upsampler = nn.PixelShuffle(upscale)
    def forward(self, x):
        out = x
        for m in self.body: out = m(out)
        return self.upsampler(out) + F.interpolate(x, scale_factor=self.upscale, mode="nearest")

def load(denoise):
    sd = torch.load(MODEL, map_location="cpu")
    sd = sd.get("params", sd.get("params_ema", sd))
    wdn = MODEL.replace("realesr-general-x4v3", "realesr-general-wdn-x4v3")
    if denoise < 1 and os.path.exists(wdn):  # optional blend with the "without denoise" model
        sd2 = torch.load(wdn, map_location="cpu"); sd2 = sd2.get("params", sd2.get("params_ema", sd2))
        sd = {k: denoise * sd[k] + (1 - denoise) * sd2[k] for k in sd}
    m = SRVGGNetCompact(); m.load_state_dict(sd, strict=True); m.eval()
    return m

def probe(p):
    o = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                 "stream=width,height,r_frame_rate,nb_frames:format=duration", "-of", "default=nw=1", p]).decode()
    d = dict(l.split("=", 1) for l in o.split())
    return d

def main():
    a = sys.argv[1:]
    if len(a) < 2: print(__doc__); sys.exit(1)
    g = lambda k, d: a[a.index(k) + 1] if k in a else d
    src, out = a[0], a[1]
    W, H = int(g("--w", 1080)), int(g("--h", 1920))
    torch.set_num_threads(int(g("--threads", os.cpu_count() or 4)))
    model = load(float(g("--denoise", 1.0)))
    # decode at display orientation (ffmpeg autorotates)
    tmp = subprocess.check_output(["ffmpeg", "-v", "error", "-i", src, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    info = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-frames:v", "1", "-f", "null", "-"], capture_output=True)
    d = probe(src)
    # find displayed size from one decoded frame via ffprobe of a png
    png = subprocess.check_output(["ffmpeg", "-v", "error", "-i", src, "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"])
    w = int.from_bytes(png[16:20], "big"); h = int.from_bytes(png[20:24], "big")
    fps = d["r_frame_rate"]; dur = float(d["duration"])
    n_est = int(dur * eval(fps))
    if "--half" in a: w, h = w // 2 // 2 * 2, h // 2 // 2 * 2
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-vf", f"scale={w}:{h}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    run = lambda x: model(x)
    try:
        import openvino as ov
        cm = ov.Core().compile_model(ov.convert_model(model, example_input=torch.zeros(1, 3, h, w)), "CPU",
                                     {"INFERENCE_PRECISION_HINT": "f32", "PERFORMANCE_HINT": "LATENCY"})
        run = lambda x: torch.from_numpy(cm(x.numpy())[0]); print("  OpenVINO CPU")
    except Exception as e: print("  torch CPU (no OpenVINO):", str(e)[:80])
    if "--test" in a:
        raw = dec.stdout.read(w * h * 3); dec.kill()
        x = torch.from_numpy(np.frombuffer(raw, np.uint8).reshape(h, w, 3).copy()).permute(2, 0, 1)[None].float() / 255
        t = time.time()
        with torch.inference_mode(): y = model(x)
        el = time.time() - t
        img = (y[0].clamp(0, 1).permute(1, 2, 0).numpy() * 255).round().astype(np.uint8)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{img.shape[1]}x{img.shape[0]}", "-i", "-",
                        "-vf", f"scale={W}:{H}:flags=lanczos", out], input=img.tobytes(), check=True)
        print(f"  1 frame {w}x{h} in {el:.2f}s -> est. {el * n_est / 60:.1f} min for {n_est} frames")
        return
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w * 4}x{h * 4}", "-r", fps, "-i", "-",
                            "-i", src, "-map", "0:v", "-map", "1:a?", "-vf", f"scale={W}:{H}:flags=lanczos",
                            "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "copy", out], stdin=subprocess.PIPE)
    i, t0 = 0, time.time()
    while True:
        raw = dec.stdout.read(w * h * 3)
        if len(raw) < w * h * 3: break
        x = torch.from_numpy(np.frombuffer(raw, np.uint8).reshape(h, w, 3).copy()).permute(2, 0, 1)[None].float() / 255
        with torch.inference_mode(): y = run(x)
        enc.stdin.write((y[0].clamp(0, 1).permute(1, 2, 0).numpy() * 255).round().astype(np.uint8).tobytes())
        i += 1
        if i % 25 == 0:
            el = time.time() - t0; print(f"  {i}/{n_est} frames, {el / i:.2f}s/frame, ~{(n_est - i) * el / i / 60:.1f} min left", flush=True)
    enc.stdin.close(); enc.wait()
    print(f"  done: {i} frames in {(time.time() - t0) / 60:.1f} min -> {out}")

if __name__ == "__main__":
    main()
