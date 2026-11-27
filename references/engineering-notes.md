# Engineering notes: how pro-video-editor works, what was measured, what was decided

Read this before changing the pipeline. Numbers are from a 4-core i7-8665U laptop, 32 GB RAM, Intel UHD 620,
no NVIDIA GPU, Windows 11 with Smart App Control on (2026-11-27).

## Pipeline

```
upload -> transcribe.py (+ word-for-word second pass) -> analyze.py -> cut.py (pauses, fillers, retakes)
       -> looks_preview.py -> intake questions (one screen, max 4) -> autoedit.py --answers (plan.json)
       -> Claude adds graphics (humanizer wording) -> compose.py (graphics batch -> 4 parallel parts + audio -> join)
       -> stills check -> deliver
```

## Speed: methods in use (all lossless)

| Method | Where | Effect (1-min reel) |
|---|---|---|
| One browser for all graphics (`render_gfx.mjs --batch`, 3 pages at once) | compose.py -> render_gfx.mjs | no 2-3 s Chromium start per graphic |
| Reuse a frame when the DOM didn't change (`#s` innerHTML signature) | render_gfx.mjs | a 6 s card captures ~40 frames, not 180; 12 graphics in **17 s** (was 2-4 min) |
| Motion backgrounds as H.264 (crf 12) in a global cache `~/.pro-video-editor/cache/bg_<hash>.mp4` | compose.py gfx() | 12 MB instead of 0.7-1.5 GB qtrle; **0 s** after the first video in a look (was ~6 min each time) |
| Split the timeline into 4 parts rendered at once, audio mixed once, join with concat `-c copy` | compose.py render()/driver | final render **~2.5 min** (was 5-9.5 min) |
| Every input seeks to its part (`-ss`), timestamps shifted back with `setpts=+S/TB` | compose.py render(mode="video") | part 4 no longer decodes 45 s of backgrounds/mattes first |
| Absolute timeline inside each part (main input seek + setpts), output `trim` + `-frames:v N` | compose.py | parts are frame-exact; captions/animations continue across joins |
| Graphics cache per plan (params hash in `<name>.mov.json`) | compose.py gfx() | a fix re-renders only changed cards |
| No separate preview pass | SKILL.md section 4 | saves a whole render (~4 min) |
| Greedy (beam 1) full transcription + careful (beam 5) second pass only on stretched words | transcribe.py | ~55 s per minute, repeats still caught |

Result: upload to final file for a 1-minute reel went from **~11 min to ~4 min** with identical encoder settings,
resolution and frame rate. Verified: 1643 frames = 54.8 s, seamless joins at 13.7 s / 27.3 s, -14.2 LUFS.

Join safety: every part is encoded with the same x264 settings (`-preset faster -crf 19 yuv420p`), so the
concat demuxer can copy streams. If you change encoder settings, change them in one place (x264 list in render()).

## Speed: rejected (and why)

| Idea | Why not |
|---|---|
| Intel Quick Sync (h264_qsv) | faster but worse quality per bit, files up to 3x larger - breaks "no quality compromise" |
| More `-filter_complex_threads` | overlay filters barely thread; 2 threads ~ 12 threads in reports |
| Browser screencast instead of screenshots | JPEG only - no alpha for graphics |
| CDP `beginFrame` capture (~5 ms/frame) | Linux only |
| Lower fps / resolution | visible quality loss |
| Intel iGPU (OpenVINO GPU) for AI models | gave WRONG output (max error ~26) for Real-ESRGAN on UHD 620 - CPU only |
| Cloud rendering / GPU rental | costs money, uploads people's videos, not simple |

Next candidates: profile the per-frame filters in the final render (grade + vignette + CAS + punch-in scale +
libass at 1080x1920 is most of the remaining ~2.5 min); skip filters on segments where nothing changes.

## Retakes and repeated words

Whisper tidies speech: a repeated phrase is written once and one word is stretched over both takes
(e.g. "anything" 2.1 s instead of ~0.3 s). Fix in two layers:
1. transcribe.py: every word longer than 0.7 s -> re-transcribe that window (+-2 s) with beam 5 and a
   disfluent "VERBATIM" initial prompt; splice in when it finds more words.
2. cut.py `find_retakes`: a phrase restarted within 12 s and 14 words (same first word, >= 60% token match)
   -> cut the earlier take, keep the last; immediate doubles ("I I"); idioms like "step by step",
   "section by section", "day after day" are protected (IDIOM_LINK).
Tested on the AI-editor reel: all 3 retakes found automatically, 59.3 s -> 54.6 s.

## Auto face framing

face_frame.py: BiRefNet-lite person mask on 3 frames (at 1/4, 1/2, 3/4) -> head = top of the mask down to
where the body is 1.7x wider than the head (shoulders), capped at 1.6x head width; face centre = 55% down the head;
median over frames. ~40 s on the laptop with half the CPU threads, started by `autoedit --analyze` as a detached
process so it overlaps the intake. Tested: low framing 0.60 (hand-picked 0.68), normal framing 0.40.
Why it matters: a wrong face_y cost a second full render (~2.5 min) in the 13:50 test.

## Background swap

| Method | Extra time / min | Status |
|---|---|---|
| Green/blue screen or contrasting plain wall: ffmpeg chromakey/colorkey + despill | ~10 s | **ON** (`features.json` background_swap = "keyable_only") |
| Cream/beige wall: MIT BiRefNet-lite matte on 1 frame per second + ffmpeg key in the edge band (scripts/matte.py --every 1) | 11-20 min (11 s per AI frame idle, 22 s busy) | built, OFF (set "all") |
| BiRefNet every frame | ~6 h | request only |
| Plain colour key on a cream wall | - | fails: lit skin matches the wall, holes in the face |

analyze.py decides `keyable` from border uniformity and how much of the subject shares the key colour.
Ideas to make the matte path faster (not built): run BiRefNet at 512 px (export a dynamic-size ONNX from the MIT
weights, ~4x faster), start it right after upload so it runs during the intake, key every 2 s when the speaker
is still. MODNet (Apache-2.0) would be ~1-2 min per minute but breaks the MIT/ISC rule.

## Windows Smart App Control

New native libraries (numpy, av, scipy, onnxruntime DLLs) can be blocked on first load and allowed seconds
later once Windows has checked them online. install.ps1 retries a warm-up import 6 times with 30 s waits.
`av` is pinned to 18.1.0 (newer builds were blocked); audio is decoded by ffmpeg, not av. Never disable or
work around Smart App Control.

## Licence rule

Bundled code must be MIT or ISC. Non-MIT dependencies are opt-in installer flags (-AllowNonMIT, -WithRNNoise).
See LICENSES.md.


## Render speed round 2 (2026-11-27) - measured on part 1 of 4 (14 s, 1080x1920, Clean cards)
- Upstream of an `overlay ... enable=` window, ffmpeg still computes every frame. Biggest waste: grading the
  upscaled 1080x1920 frame. Crop + grade at source resolution, then scale: 54.6 s -> 20.5 s (filters only).
- Zoom branch (scale to 1.14x + crop every frame, shown only at punch-ins): 11.6 s. Replaced by `sendcmd` driving
  `crop@z` w/h/x/y at the punch times before the single upscale - zero extra cost, same framing.
- After that the encoder dominates: x264 faster CRF 19 44.2 s; veryfast CRF 18 33.1 s (SSIM 0.98753 vs 0.98765
  against a CRF 10 reference); h264_qsv ICQ 20 30.0 s (0.98673); ICQ 17 39.7 s (0.98803, 15 MB).
- Whole reel: 223 s -> 125 s. Old vs new SSIM 0.969 overall; the only differing pixels are the faint moving paper
  texture of the card background (loop phase), text/graphics/face identical.
