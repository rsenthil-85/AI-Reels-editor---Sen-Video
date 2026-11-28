"""transcribe.py - word-level transcript of a video/audio file (faster-whisper, CPU).

    python transcribe.py input.mp4 out_dir [--model small] [--lang auto|en|ta|hi|te|kn|ml|mr|gu] [--beam 1|5]

--lang auto (default) detects the spoken language. English uses the fast small model; any other language uses
large-v3-turbo when it has been downloaded (once, ~1.6 GB). --model forces one model for everything.

Writes out_dir/words.json  [{"w": "word", "s": 1.23, "e": 1.51}]  and out_dir/transcript.srt
(one cue per sentence-ish chunk, so yt-edit/yt-chapters/yt-shorts can read it).
"""
import json, os, re, sys

# A prompt full of natural stumbles makes Whisper write what was SAID (repeats, restarts, fillers) instead of
# a tidied version - without it a repeated phrase hides inside one long "word" and cannot be cut.
VERBATIM = ("Umm, so, so I, I was, uh, I was like... like, you know, I I mean, the the thing is, um, it it it shows me, "
            "uh, before, before it edits. Claude, ChatGPT, AI, side hustle, $1,000.")

BIG = "large-v3-turbo"   # for every language that is not English
LANGS = {"en": "English", "ta": "Tamil", "hi": "Hindi", "te": "Telugu", "kn": "Kannada", "ml": "Malayalam", "mr": "Marathi",
         "gu": "Gujarati", "bn": "Bengali", "pa": "Punjabi", "ur": "Urdu"}

def srt_time(t):
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"

def main():
    a = sys.argv[1:]
    if len(a) < 2: print(__doc__); sys.exit(1)
    src, out = a[0], a[1]
    picked = a[a.index("--model") + 1] if "--model" in a else os.environ.get("WHISPER_MODEL")
    lang = a[a.index("--lang") + 1] if "--lang" in a else "auto"
    os.makedirs(out, exist_ok=True)
    from faster_whisper import WhisperModel
    load = lambda name, **k: WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4, **k)
    m = load(picked or "small")
    beam = int(a[a.index("--beam") + 1]) if "--beam" in a else 1   # full pass greedy (fast); hidden repeats are recovered by the careful second pass below
    # decode with ffmpeg (16 kHz mono float) instead of PyAV: faster, and avoids av's decoder entirely
    import subprocess, numpy as np
    pcm = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, np.float32)
    def note(text):
        print("  " + text, flush=True)
        try: import livelog; livelog.note(out, text)
        except Exception: pass
    if lang == "auto":   # which language is spoken? (first 30 s; unsure -> English)
        lang, prob, _ = m.detect_language(audio[:16000 * 30])
        if prob < 0.5: lang = "en"
        note(f"language: {LANGS.get(lang, lang)} ({prob:.0%} sure)")
    if lang != "en" and not picked:
        # the small model writes broken text for Tamil, Hindi, Telugu... (measured: a 30 s Tamil clip came out as one
        # word repeated); large-v3-turbo (MIT, ~1.6 GB, downloaded once with the user's OK) handles them
        try: m = load(BIG, local_files_only=True); note(f"{LANGS.get(lang, lang)} speech: using the bigger speech model")
        except Exception: note(f"{LANGS.get(lang, lang)} speech: the bigger speech model is not downloaded, captions may be wrong (ask to download {BIG})")
    prompt = VERBATIM if lang == "en" else None   # an English prompt pushes other languages into English
    json.dump({"lang": lang}, open(os.path.join(out, "lang.json"), "w"))
    mixed = lang != "en" and "--lang-strict" not in a
    if mixed:
        # Indian speakers mix languages (Tamil + English...). Forcing one language for the whole clip made broken text
        # (measured, 37 s Tamil/English clip: 386 s and nonsense). Per-sentence language, careful decoding and skipping
        # silence gave clean sentences in 95 s - written in English, the meaning of what was said.
        segs, info = m.transcribe(audio, multilingual=True, word_timestamps=True, beam_size=5, vad_filter=True,
                                  condition_on_previous_text=False, no_repeat_ngram_size=3)
        note("listening sentence by sentence (speech can mix languages)")
    else:
        segs, info = m.transcribe(audio, language=lang, word_timestamps=True, beam_size=beam,
                                  vad_filter=False, condition_on_previous_text=False,
                                  initial_prompt=prompt)
    words, cues = [], []
    for sg in segs:
        ws = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for w in (sg.words or []) if w.word.strip()]
        words += ws
        if ws: cues.append((ws[0]["s"], ws[-1]["e"], " ".join(x["w"] for x in ws)))
        print(f"\r  {sg.end:7.1f}s / {info.duration:.0f}s", end="", flush=True)
        try:   # live edit page (live.py): show how far the listening is
            import livelog; livelog.step(out, "analyse", "doing", f"heard {sg.end / max(info.duration, 1):.0%} of your video")
        except Exception: pass
    print()
    # second pass: a word stretched over > 0.7 s usually hides a repeat or restart Whisper tidied away.
    # Re-transcribe just those few seconds word-for-word and splice the result in when it finds more words.
    def stretched(ws): return [w for w in ws if w["e"] - w["s"] > 0.7]
    wins = []
    # (English only: on mixed-language speech it re-heard the gaps as new words and took 9x longer - measured 883 s vs 95 s)
    for w in (stretched(words) if not mixed else []):
        lo, hi = max(0.0, w["s"] - 2.0), w["e"] + 2.0
        if wins and lo <= wins[-1][1]: wins[-1][1] = max(wins[-1][1], hi)
        else: wins.append([lo, hi])
    fixed = 0
    for lo, hi in wins:
        clip = audio[int(lo * 16000):int(hi * 16000)]
        sg2, _ = m.transcribe(clip, language=None if mixed else lang, multilingual=mixed, word_timestamps=True, beam_size=5,
                              condition_on_previous_text=False, initial_prompt=prompt)
        new = [{"w": x.word.strip(), "s": round(x.start + lo, 3), "e": round(x.end + lo, 3)} for sg in sg2 for x in (sg.words or []) if x.word.strip()]
        new = [x for x in new if lo + 0.3 <= x["s"] <= hi - 0.3]                      # trust the middle of the window
        if not new: continue
        a0, a1 = new[0]["s"], new[-1]["e"]
        old = [x for x in words if a0 - 0.05 <= x["s"] <= a1]
        if len(new) > len(old):
            words = [x for x in words if x["s"] < a0 - 0.05] + new + [x for x in words if x["s"] > a1]
            fixed += 1
    if fixed: print(f"  word-for-word pass restored hidden repeats in {fixed} place(s)")
    merged = []  # whisper splits numbers: "$1" ",000" / "50" "%" -> one word
    for w in words:
        if merged and (re.match(r"^[,.]\d", w["w"]) or w["w"] in ("%", "k", "K")):
            merged[-1]["w"] += w["w"]; merged[-1]["e"] = w["e"]
        else: merged.append(dict(w))
    words = merged
    if mixed and words:
        latin = sum(all(ord(ch) < 0x250 for ch in w["w"]) for w in words) / len(words)
        if latin > 0.8: note(f"captions are in English: the meaning of your {LANGS.get(lang, lang)} speech, not word for word")
    json.dump(words, open(os.path.join(out, "words.json"), "w", encoding="utf-8"), ensure_ascii=False)
    with open(os.path.join(out, "transcript.srt"), "w", encoding="utf-8") as f:
        for i, (s, e, t) in enumerate(cues, 1): f.write(f"{i}\n{srt_time(s)} --> {srt_time(e)}\n{t}\n\n")
    print(f"  {len(words)} words, language {info.language}, -> {out}")

if __name__ == "__main__":
    main()
