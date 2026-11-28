"""autoedit.py - raw video to finished edit in two phases, with a short style brief in between.

  Phase 1 (analyse, ~1 min):  python autoedit.py input.mp4 --analyze [--drop "a-b,..."] [--lang auto|en|ta|hi...]
      transcribe -> analyse -> cut dead air/fillers/retakes -> <name>_edit/analysis.json + intake.json + sheet.jpg
      intake.json holds the recommended answer for every brief question (see SKILL.md "Intake").
  Phase 2 (edit):             python autoedit.py input.mp4 --answers answers.json [--preview] [--no-render]
      builds plan.json from the answers + the matching preset, then renders.
  One shot (no questions):    python autoedit.py input.mp4 [--preset NAME]      (= recommended answers)

answers.json:
  {"style": "mixed|studio|simple", "format": "reel_full|reel_60|reel_30|long", "look": "paper|highlight|navy|mint|dark",
   "captions": "karaoke|pill|minimal|duo|stack|none"   (left out = the style's own caption),
   "extras": ["bg_replace","motion_bg","transitions","graphics","zooms","music","effects","broll"],
   "music_mood": "lofi|chill|upbeat|corporate|tech|cinematic", "save_profile": true}
Always on, never asked: dead-air/filler cuts, clean voice + background-voice gate, colour grade, -14 LUFS, humanizer.
The last answers are saved to <install>/.state/profile.json ("same as last time?").
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
PROFILE = os.path.join(os.environ.get("PVE_STATE") or os.path.join(ROOT, ".state"), "profile.json")   # per install
CAPS = {"karaoke": "bold", "pill": "pill", "minimal": "minimal", "duo": "duo", "stack": "stack"}
STYLES = json.load(open(os.path.join(ROOT, "styles", "edit_styles.json"), encoding="utf-8"))

def run(args):
    print("  >", os.path.basename(args[1]), flush=True)
    subprocess.run(args, check=True)

def load(p): return json.load(open(p, encoding="utf-8"))

def recommend(an, preset_name, presets, words=()):
    pre = presets[preset_name]
    # style: a spoken list ("first ... second ... third") suits Bold B-roll; long-form and other talk suit Clean cards
    txt = " ".join(w["w"].lower() for w in words)
    import re
    listy = (sum(k in txt for k in ("first", "second", "third", "fourth", "number one", "number two", "step one", "step two"))
             + len(set(re.findall(r"(?:step|number|tip|no\.?)\s*(\d+|one|two|three|four|five)", txt)))) >= 2
    style = "studio" if (listy and pre.get("format") != "long") else "mixed"
    fmt = "long" if pre.get("format") == "long" else "reel_full"
    if fmt == "reel_full" and an["duration"] > 100: fmt = "reel_60"
    look = pre.get("theme") or ("paper" if an.get("ai_topic") else "highlight")
    caps = {"bold": "karaoke", "pill": "pill", "minimal": "minimal"}.get(pre.get("caption_style"), "karaoke")
    if pre.get("captions") is False: caps = "none"
    extras = ["transitions", "graphics", "zooms", "music"] + (["motion_bg"] if fmt != "long" else [])
    feats = json.load(open(os.path.join(ROOT, "styles", "features.json"))) if os.path.exists(os.path.join(ROOT, "styles", "features.json")) else {}
    if feats.get("background_swap") in (True, "keyable_only", "all") and (an.get("background") or {}).get("keyable"): extras.insert(0, "bg_replace")
    mood = (pre.get("music") or "auto:lofi").split(":")[-1]
    caps = STYLES[style]["caption"] if pre.get("captions") is not False else "none"
    if style == "studio": extras = [x for x in extras if x not in ("motion_bg", "transitions")]
    return {"style": style, "format": fmt, "look": look, "captions": caps, "extras": extras, "music_mood": mood}

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    g = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    src = os.path.abspath(a[0]); name = os.path.splitext(os.path.basename(src))[0]
    work = os.path.join(os.path.dirname(src), name + "_edit"); os.makedirs(work, exist_ok=True)
    W = lambda f: os.path.join(work, f)
    presets = load(os.path.join(ROOT, "styles", "presets.json")); themes = load(os.path.join(ROOT, "styles", "themes.json"))

    sys.path.insert(0, HERE); import livelog as LL
    if "--analyze" in a: LL.reset(work, video=os.path.basename(src), src=src)
    # ---- phase 1: transcribe, analyse, cut (all cached)
    LL.step(work, "analyse", "doing", "turning your speech into words")
    if not os.path.exists(W("words.json")):
        run([PY, os.path.join(HERE, "transcribe.py"), src, work, "--lang", g("--lang", "auto")] + (["--model", g("--model")] if g("--model") else []))
    if not os.path.exists(W("analysis.json")) or "--analyze" in a:
        run([PY, os.path.join(HERE, "analyze.py"), src, work, "--words", W("words.json")])
    an = load(W("analysis.json"))
    speech = (an.get("speech_share") or 0) >= 0.2
    nw = len(load(W("words.json"))) if os.path.exists(W("words.json")) else 0
    LL.step(work, "analyse", "done", f"{nw} words heard, {an['duration']:.0f} s video", duration=an["duration"])
    LL.step(work, "cut", "doing", "finding pauses, umms and repeated lines")
    if speech and (not os.path.exists(W("cut.mp4")) or g("--drop") is not None):
        cut = [PY, os.path.join(HERE, "cut.py"), src, W("words.json"), work]
        if g("--drop"): cut += ["--drop", g("--drop")]
        run(cut)
    pname = g("--preset", an["preset"])
    rec = recommend(an, pname, presets, load(W("words.json")) if os.path.exists(W("words.json")) else ())
    prof = load(PROFILE) if os.path.exists(PROFILE) else None
    vid = W("cut.mp4") if speech else src
    intake = {"preset": pname, "why": an["why"], "recommended": rec, "last_profile": prof, "background": an.get("background"),
              "cut_seconds": float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vid]).decode()),
              "themes": {k: {"label": v["label"], "looks_like": v["looks_like"], "note": v["note"]} for k, v in themes.items()},
              "styles": {k: {"label": v["label"], "question": v["question"], "uses_look": v["uses_look"]} for k, v in STYLES.items()}}
    json.dump(intake, open(W("intake.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    if speech:
        segs = load(W("segments.json")) if os.path.exists(W("segments.json")) else []
        LL.step(work, "cut", "done", f"{an['duration']:.0f} s down to {intake['cut_seconds']:.0f} s ({max(0, len(segs) - 1)} gaps removed)",
                cut_seconds=intake["cut_seconds"])
    else: LL.step(work, "cut", "done", "no speech, nothing to cut")
    if "--analyze" in a and not os.path.exists(W("choice.json")):   # the user may have pressed Start while we analysed: keep their choice
        LL.step(work, "style", "todo", "waiting for you: pick a style above and press Start editing")
    if "--analyze" in a:
        # auto face framing: start it now in the background; it finishes while the user answers the questions
        if not os.path.exists(W("face.json")) or g("--drop") is not None:
            if os.path.exists(W("face.json")): os.remove(W("face.json"))
            flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
            subprocess.Popen([PY, os.path.join(HERE, "face_frame.py"), vid, work], stdout=open(W("face.log"), "w"),
                             stderr=subprocess.STDOUT, creationflags=flags)
        print(json.dumps({"preset": pname, "why": an["why"], "recommended": rec, "cut_seconds": round(intake["cut_seconds"], 1),
                          "has_profile": bool(prof)}, ensure_ascii=False))
        return

    # ---- phase 2: answers -> plan -> render
    ans = dict(rec)
    ua = (load(g("--answers")) if os.path.exists(g("--answers")) else json.loads(g("--answers"))) if g("--answers") else {}
    ans.update(ua)
    ex = set(ans.get("extras", []))
    fp = os.path.join(ROOT, "styles", "features.json"); feats = json.load(open(fp)) if os.path.exists(fp) else {}
    th = themes.get(ans.get("look", "paper"), themes["paper"])
    fmt = "long" if ans.get("format") == "long" else "reel"
    sty = STYLES.get(ans.get("style", "mixed"), STYLES["mixed"])
    if "captions" not in ua: ans["captions"] = sty["caption"]          # captions follow the chosen style unless asked
    pre = presets[pname]
    plan = {"format": fmt, "src": "cut.mp4" if speech else src, "words": "words_cut.json" if speech else "words.json",
            "out": g("--out", os.path.join(os.path.dirname(src), name + "_edited.mp4")),
            "face_x": 0.5, "face_y": 0.45 if an["orientation"] == "vertical" else 0.40,
            "punch": "auto" if "zooms" in ex else [], "inserts": [], "overlays": [],
            "captions": ans.get("captions", "karaoke") != "none", "caption_style": CAPS.get(ans.get("captions"), "bold"),
            "caption_y": pre.get("caption_y", 0.80), "accent": th["accent"], "theme": th["theme"], "panel_base": th["panel_base"],
            "grade": True, "voice_clean": True, "speech_gate": speech, "transitions": "transitions" in ex,
            "_preset": pname, "_answers": ans,
            "_todo": [x for x in ("graphics", "effects", "broll") if x in ex]}   # Claude adds these (they need judgement)
    plan["layout"] = sty["layout"]; plan["grade"] = sty["grade"]; plan["_style"] = ans.get("style", "mixed")
    plan["_style_graphics"] = sty["graphics"]
    if sty.get("split_style"): plan["split_style"] = sty["split_style"]
    if ans.get("caption_color"): plan["caption_acc"] = ans["caption_color"]   # picked on the edit page
    if sty["layout"] == "face": plan["caption_fs"] = 92
    if sty["layout"] == "face" and plan["caption_style"] == "stack": plan["stack_y"] = 0.70   # under the face, not across it          # face only: captions carry the screen, make them bigger
    if sty["layout"] == "tutorial": plan["caption_y"] = 0.655           # between the zoomed screen (top 4-62%) and the face bubble
    if sty.get("needs"): plan["_todo"].append(f"{sty['needs']}: use the files the user named (choice.json materials); ask if none")
    if sty.get("accent"): plan["accent"] = sty["accent"]
    if not sty["transitions"]: plan["transitions"] = False
    if "motion_bg" in ex and sty["layout"] != "studio": plan["panel_bg"] = "auto:" + th["panel_bg_style"]
    bgi = an.get("background") or {}
    if "bg_replace" in ex:
        if bgi.get("keyable"):
            plan["bg_replace"] = {"bg": ans.get("bg_source", "auto:" + th["panel_bg_style"]), "key": bgi["key"],
                                  "base": th["panel_base"], "similarity": 0.12 if bgi["kind"].endswith("screen") else 0.14}
            if bgi.get("flat"):   # flat digital green/blue: tight RGB key (see analyze.py)
                plan["bg_replace"].update(method="colorkey", similarity=0.06, blend=0.03)
        elif feats.get("background_swap") == "all" and bgi.get("kind") in ("plain_wall", "busy") and os.path.exists(os.path.join(ROOT, "assets", "models", "birefnet_lite.onnx")):
            # wall too close to skin colour: matte-assisted key (MIT BiRefNet on one frame per second, ~11 s each)
            md = W("matte_moving")
            if not os.path.exists(os.path.join(md, "core.mp4")):
                print(f"  building moving matte (~{intake['cut_seconds'] * 11 / 60:.0f} min on a laptop CPU)", flush=True)
                run([PY, os.path.join(HERE, "matte.py"), W("cut.mp4") if speech else src, md, "--every", "1.0"])
            plan["bg_replace"] = {"bg": ans.get("bg_source", "auto:" + th["panel_bg_style"]), "key": bgi["key"], "base": th["panel_base"],
                                  "similarity": 0.14, "blend": 0.08, "matte": "matte_moving"}
        else:
            print("  background swap skipped: this footage can't be keyed cleanly -", bgi.get("advice"))
    # auto face framing result (started by --analyze); wait for it if it is still running
    import time
    for _ in range(120):
        if os.path.exists(W("face.json")): break
        time.sleep(1)
    if os.path.exists(W("face.json")):
        fj = load(W("face.json")); plan["face_x"], plan["face_y"] = fj["face_x"], fj["face_y"]
        print(f"  face framing: {fj['method']} -> face at {fj['face_y']:.0%} of the height")
    if an.get("low_res"): plan["sharpen"] = 0.35
    if "music" in ex: plan["music"] = "auto:" + ans.get("music_mood", "lofi"); plan["music_db"] = pre.get("music_db", -23)
    plan["sfx_density"] = ans.get("sfx_density", "medium" if sty["layout"] == "studio" else pre.get("sfx_density", "medium"))   # ref 7: ~57 hits/min
    target = {"reel_60": 60, "reel_30": 30}.get(ans.get("format"))
    if target and intake["cut_seconds"] > target + 5:
        plan["_todo"].append(f"trim to ~{target}s: pick the strongest spans with skills/yt-shorts, re-run --analyze with --drop")
    if os.path.exists(W("plan.json")) and "--fresh-plan" not in a:
        old = load(W("plan.json")); plan["inserts"], plan["overlays"] = old.get("inserts", []), old.get("overlays", [])
    json.dump(plan, open(W("plan.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    LL.step(work, "style", "done", f"{sty['label']}, {plan['caption_style']} captions" + (", music" if plan.get("music") else ""),
            style=sty["label"])
    if ans.get("save_profile", True):
        os.makedirs(os.path.dirname(PROFILE), exist_ok=True)
        json.dump({k: ans[k] for k in ("style", "format", "look", "captions", "extras", "music_mood") if k in ans}, open(PROFILE, "w"), indent=1)
    print("  plan.json written; still to add by hand:", plan["_todo"] or "nothing")
    if "--no-render" not in a:
        run([PY, os.path.join(HERE, "compose.py"), W("plan.json")] + (["--preview"] if "--preview" in a else []))

if __name__ == "__main__":
    main()
