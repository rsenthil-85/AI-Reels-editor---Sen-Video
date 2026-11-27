"""analyze.py - look at a video and recommend a style preset (styles/presets.json).

    python analyze.py input.mp4 out_dir [--words words.json]

Writes out_dir/analysis.json and out_dir/sheet.jpg (12-frame contact sheet - LOOK at it: faces, screen
recordings, number of people and setting are judged by eye, not by this script).
Measures: displayed size/orientation, duration, fps, loudness, noise floor, speech share and pace (if words.json),
scene-change rate, topic keywords, then applies the preset rules below.
"""
import json, os, re, subprocess, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
AI_WORDS = {"ai", "chatgpt", "claude", "gpt", "gemini", "prompt", "automation", "agent", "agents", "website", "app", "tool",
            "tools", "money", "income", "hustle", "business", "client", "clients", "code", "coding", "build", "startup", "saas"}
STOP = set("the a an and or but so to of in on for with is are was were be been it this that these those you your i me my we our "
           "they them he she his her as at by from what how why when then than there here just like know going do does did can "
           "will would should could have has had not no yes if about into up out one all any more most very really get got".split())

def ff(args): return subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-nostats"] + args, capture_output=True, text=True).stderr

def main():
    a = sys.argv[1:]
    if len(a) < 2: print(__doc__); sys.exit(1)
    src, out = a[0], a[1]; os.makedirs(out, exist_ok=True)
    wj = a[a.index("--words") + 1] if "--words" in a else None
    pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,r_frame_rate",
                                             "-of", "json", src]))
    dur = float(pr["format"]["duration"]); has_audio = any(s["codec_type"] == "audio" for s in pr["streams"])
    vs = [s for s in pr["streams"] if s["codec_type"] == "video"][0]; fps = round(eval(vs["r_frame_rate"]), 2)
    png = subprocess.check_output(["ffmpeg", "-nostdin", "-v", "error", "-i", src, "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"])
    w = int.from_bytes(png[16:20], "big"); h = int.from_bytes(png[20:24], "big")
    orient = "vertical" if h > w * 1.1 else "horizontal" if w > h * 1.1 else "square"
    res = {"file": os.path.abspath(src), "width": w, "height": h, "orientation": orient, "duration": round(dur, 2), "fps": fps,
           "low_res": min(w, h) < 720}
    # scene changes per minute (downscaled for speed)
    sc = ff(["-i", src, "-vf", "scale=160:-2,select='gt(scene,0.30)',showinfo", "-an", "-f", "null", "-"]).count("pts_time")
    res["scene_changes_per_min"] = round(sc / dur * 60, 1)
    if has_audio:
        vd = ff(["-i", src, "-vn", "-af", "volumedetect", "-f", "null", "-"])
        m = re.search(r"mean_volume: (-?[\d.]+)", vd); res["mean_volume_db"] = float(m.group(1)) if m else None
        st = ff(["-i", src, "-vn", "-af", "astats=metadata=1:reset=0.05,ametadata=print:key=lavfi.astats.Overall.RMS_level", "-f", "null", "-"])
        lv = sorted(float(x) for x in re.findall(r"RMS_level=(-?[\d.]+)", st) if x != "-inf")
        if lv: res["noise_floor_db"] = round(lv[int(len(lv) * 0.1)], 1); res["noisy"] = res["noise_floor_db"] > -45
    # transcript stats
    preset_hint = []
    if wj and os.path.exists(wj):
        words = json.load(open(wj, encoding="utf-8"))
        talk = sum(x["e"] - x["s"] for x in words)
        res["speech_share"] = round(talk / dur, 2); res["words_per_min"] = round(len(words) / dur * 60)
        toks = [re.sub(r"[^a-z0-9$]", "", x["w"].lower()) for x in words]
        kw = Counter(t for t in toks if t and t not in STOP and len(t) > 2)
        res["keywords"] = [k for k, _ in kw.most_common(15)]
        res["ai_topic"] = sum(kw[k] for k in AI_WORDS) >= 4
        res["opening_line"] = " ".join(x["w"] for x in words[:14])
    else:
        res["speech_share"] = None
    # background check for the "change my real background" option (chroma key, no AI model):
    # key = median border colour; keyable only if the border is uniform AND the subject area barely shares the colour
    try:
        import io, numpy as np
        from PIL import Image
        bd, ov = [], []
        for tt in (0.2, 0.5, 0.8):
            pngb = subprocess.check_output(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{dur * tt:.2f}", "-i", src, "-frames:v", "1",
                                            "-vf", "scale=160:-2", "-f", "image2pipe", "-c:v", "png", "-"])
            arr = np.asarray(Image.open(io.BytesIO(pngb)).convert("RGB")).astype(float); hh, ww = arr.shape[:2]
            bd.append(np.concatenate([arr[: int(hh * .12)].reshape(-1, 3), arr[:, : int(ww * .08)].reshape(-1, 3), arr[:, -int(ww * .08):].reshape(-1, 3)]))
            ov.append(arr[int(hh * .3): int(hh * .8), int(ww * .3): int(ww * .7)].reshape(-1, 3))
        bd = np.concatenate(bd); ov = np.concatenate(ov); key = np.median(bd, axis=0)
        uniform = float(np.mean(np.linalg.norm(bd - key, axis=1) < 40))          # share of border close to the key
        overlap = float(np.mean(np.linalg.norm(ov - key, axis=1) < 55))          # subject pixels that would vanish
        mx, mn = key.max(), key.min(); sat = (mx - mn) / (mx + 1e-6)
        kind = "green_screen" if (key[1] > key[0] + 40 and key[1] > key[2] + 40 and sat > .35) else                "blue_screen" if (key[2] > key[0] + 40 and key[2] > key[1] + 20 and sat > .35) else                "plain_wall" if uniform > .6 else "busy"
        keyable = kind in ("green_screen", "blue_screen") and overlap < .05 or kind == "plain_wall" and overlap < .02 and uniform > .75
        res["background"] = {"kind": kind, "key": "#%02X%02X%02X" % tuple(int(v) for v in key), "uniform": round(uniform, 2),
                             "subject_overlap": round(overlap, 3), "keyable": bool(keyable),
                             "advice": None if keyable else "record in front of a green screen or a smooth wall whose colour is far from your skin and clothes, lit evenly"}
    except Exception as e:
        res["background"] = {"kind": "unknown", "keyable": False, "error": str(e)[:80]}
    # rules
    sp = res.get("speech_share") or 0
    if sp < 0.2: preset = "cinematic-montage"
    elif orient == "vertical" or (orient == "square" and dur <= 180):
        preset = "ai-explainer-reel" if res.get("ai_topic") else "talking-head-reel"
    elif dur > 180:
        preset = "tutorial-long" if res["scene_changes_per_min"] < 4 and res.get("ai_topic") else "talking-head-long"
    else:
        preset = "talking-head-reel"
    res["preset"] = preset
    res["why"] = (f"{orient}, {dur:.0f}s, speech {sp:.0%}" + (", AI/tech topic" if res.get("ai_topic") else "")
                  + (", noisy audio -> voice clean ON" if res.get("noisy") else "") + (", low resolution -> sharpen / optional upscale" if res["low_res"] else ""))
    # contact sheet
    n = 12; step = dur / (n + 1)
    tiles = []
    for i in range(n):
        p = os.path.join(out, f"_s{i}.jpg")
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{step * (i + 1):.2f}", "-i", src, "-frames:v", "1",
                        "-vf", "scale=-2:270" if orient != "horizontal" else "scale=320:-2", p]); tiles.append(p)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", os.path.join(out, "_s%d.jpg"), "-vf", "tile=6x2", os.path.join(out, "sheet.jpg")])
    for p in tiles:
        try: os.remove(p)
        except OSError: pass
    presets = json.load(open(os.path.join(HERE, "..", "styles", "presets.json"), encoding="utf-8"))
    res["preset_settings"] = presets[preset]
    json.dump(res, open(os.path.join(out, "analysis.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps({k: res[k] for k in ("orientation", "duration", "speech_share", "preset", "why")}, ensure_ascii=False))

if __name__ == "__main__":
    main()
