"""transcribe.py - word-level transcript of a video/audio file (faster-whisper, CPU).

    python transcribe.py input.mp4 out_dir [--model small] [--lang en|ta|hi|auto] [--beam 1|5]

Writes out_dir/words.json  [{"w": "word", "s": 1.23, "e": 1.51}]  and out_dir/transcript.srt
(one cue per sentence-ish chunk, so yt-edit/yt-chapters/yt-shorts can read it).
"""
import json, os, re, sys

# A prompt full of natural stumbles makes Whisper write what was SAID (repeats, restarts, fillers) instead of
# a tidied version - without it a repeated phrase hides inside one long "word" and cannot be cut.
VERBATIM = ("Umm, so, so I, I was, uh, I was like... like, you know, I I mean, the the thing is, um, it it it shows me, "
            "uh, before, before it edits. Claude, ChatGPT, AI, side hustle, $1,000.")

def srt_time(t):
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"

def main():
    a = sys.argv[1:]
    if len(a) < 2: print(__doc__); sys.exit(1)
    src, out = a[0], a[1]
    model = a[a.index("--model") + 1] if "--model" in a else os.environ.get("WHISPER_MODEL", "small")
    lang = a[a.index("--lang") + 1] if "--lang" in a else "en"
    os.makedirs(out, exist_ok=True)
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    beam = int(a[a.index("--beam") + 1]) if "--beam" in a else 1   # full pass greedy (fast); hidden repeats are recovered by the careful second pass below
    # decode with ffmpeg (16 kHz mono float) instead of PyAV: faster, and avoids av's decoder entirely
    import subprocess, numpy as np
    pcm = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, np.float32)
    segs, info = m.transcribe(audio, language=None if lang == "auto" else lang, word_timestamps=True, beam_size=beam,
                              vad_filter=False, condition_on_previous_text=False,
                              initial_prompt=VERBATIM)
    words, cues = [], []
    for sg in segs:
        ws = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for w in (sg.words or []) if w.word.strip()]
        words += ws
        if ws: cues.append((ws[0]["s"], ws[-1]["e"], " ".join(x["w"] for x in ws)))
        print(f"\r  {sg.end:7.1f}s / {info.duration:.0f}s", end="", flush=True)
    print()
    # second pass: a word stretched over > 0.7 s usually hides a repeat or restart Whisper tidied away.
    # Re-transcribe just those few seconds word-for-word and splice the result in when it finds more words.
    def stretched(ws): return [w for w in ws if w["e"] - w["s"] > 0.7]
    wins = []
    for w in stretched(words):
        lo, hi = max(0.0, w["s"] - 2.0), w["e"] + 2.0
        if wins and lo <= wins[-1][1]: wins[-1][1] = max(wins[-1][1], hi)
        else: wins.append([lo, hi])
    fixed = 0
    for lo, hi in wins:
        clip = audio[int(lo * 16000):int(hi * 16000)]
        sg2, _ = m.transcribe(clip, language=None if lang == "auto" else lang, word_timestamps=True, beam_size=5,
                              condition_on_previous_text=False, initial_prompt=VERBATIM)
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
    json.dump(words, open(os.path.join(out, "words.json"), "w", encoding="utf-8"), ensure_ascii=False)
    with open(os.path.join(out, "transcript.srt"), "w", encoding="utf-8") as f:
        for i, (s, e, t) in enumerate(cues, 1): f.write(f"{i}\n{srt_time(s)} --> {srt_time(e)}\n{t}\n\n")
    print(f"  {len(words)} words, language {info.language}, -> {out}")

if __name__ == "__main__":
    main()
