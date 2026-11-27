# Changelog

## 1.10.0 - 2026-11-28
- Two new styles: **AI News** (face bubble over full-screen screenshots that zoom to the key line with a marker
  highlight, Breaking/New badges) and **Screen tutorial** (screen recording auto-zoomed to clicks and typing,
  face bubble, step badges). Both on the edit page, which asks for the screenshots / screen recording.
- New graphics: `shot` (screenshot + zoom to a focus box + marker) and `badge` (pill label with optional icon).
- `scripts/screen_zoom.py`: free, local auto-zoom for screen recordings (frame differences -> held zoom regions ->
  ffmpeg sendcmd crop), vertical output with a blurred full-screen backdrop.
- Face bubble (reels and long-form) is now cropped around the face, not the centre of the frame.

## 1.9.2 - 2026-11-27 (green screen)
- Flat digital green/blue screens (e.g. Canva background remover) count as swappable even with greenish clothes, and use a
  tight RGB colour key (similarity 0.06) instead of chromakey, which left the person partly see-through.
- Fringe fix for those keys: despill + matte pulled in ~2 px + 1 px soften (green halo on hair gone). Known trade-off:
  despill also cools green-tinted clothes (teal shirt reads navy).
- The edit page offers "Swap the background" when the analysis finds a keyable background, and refreshes once the
  analysis arrives without losing what the user already clicked.

## 1.9.1 - 2026-11-27 (speed, same quality)
- Final render 223 s -> 125 s for a 56 s Clean cards reel (measured, same machine, same plan):
  colour grade + crop at the SOURCE resolution, then one upscale (phone footage is ~576x1024: 3.5x fewer pixels);
  zoom-ins are one crop that shrinks at the punch times (sendcmd) instead of a second full-size zoomed copy of every
  frame; the inset face window is cut from the source too; x264 veryfast CRF 18 instead of faster CRF 19
  (SSIM vs near-lossless 0.98753 vs 0.98765 - same; file ~10-30% bigger).
- Intel Quick Sync was tested (30 s vs 33 s per part) but scores slightly lower and is Intel-only: not used.
- FilmCraft graphics convert 4 at a time.
- Cut: slowly spoken words (> 0.6 s) keep at least 0.4 s; they were sometimes removed whole as "silence".

## 1.9.0 - 2026-11-27
- One edit page for everything: the style gallery, describe-your-own, length, extras and "how to finish"
  (done for me / + touch up in FilmCraft) are chosen on the live page; Claude picks the choice up from choice.json
  (written by live.py, POST protected by a per-launch page token, local only). The same page then shows the edit live
  and, side by side, FilmCraft's progress with pictures of its window; "Open in FilmCraft" button after any edit.

## 1.8.0 - 2026-11-27
- Optional "Open in FilmCraft": `scripts/filmcraft_open.py` builds the finished edit live on FilmCraft's timeline
  (FilmCraft 0.20.1, free, MIT or Apache-2.0) through its documented control channel with a one-time token: kept parts
  of the original, page matte + cards, stickers at their positions, captions, music at our level. Graphics are
  converted to ProRes 4444 (FilmCraft has no qtrle decoder); phone rotation is handled when scaling the footage.
- `install.ps1 -WithFilmCraft`: downloads the portable build from the official release, checks SHA-256, unzips to
  tools/filmcraft (ignored by git) and records it in ~/.pro-video-editor/filmcraft.json.

## 1.7.0 - 2026-11-27
- Live edit page: `scripts/live.py` serves `templates/live.html` on 127.0.0.1 and the skill opens it in the browser pane
  right after upload. The user watches each step as it happens (listening %, what was cut, style, graphics n of m with
  a preview of each graphic as it lands, render % from ffmpeg progress, finished video), a clickable timeline and the
  transcript with cut words struck out. Progress comes from `scripts/livelog.py` (autoedit, transcribe, compose).
- "Describe your own" style: free text (or a reel link) mapped onto the nearest style plus overrides.

## 1.6.0 - 2026-11-27
- Instant style gallery: `assets/gallery/styles.jpg` (3 styles x 3 frames) and `looks.jpg` (4 colour looks), drawn
  with an illustrated presenter (new gfx type `presenter`, no real person). Shown the moment a video arrives, with the
  style question, while the analysis runs in the background - no wait before the first question.
  `scripts/make_gallery.py` rebuilds it in ~5 s. The looks preview on the user's own footage is now optional.

## 1.5.0 - 2026-11-27
- New editing style **Bold B-roll** (learned from the user's reference edit, ref 7): hook title band over B-roll,
  warm cinematic grade (`grade: "warm"`), full-screen B-roll or phone/tablet/laptop mock-ups (`device`) with giant
  lime numbers (`bignum`), stacked-word captions (`caption_style: "stack"`), glowing quoted CTA (`ctaword`), black
  end card (`endcard`).
- Intake asks the **editing style first** (Clean cards / Bold B-roll / Face and captions, `styles/edit_styles.json`);
  captions, layout, grade and graphics follow the style. Spoken lists ("first... second...") recommend Bold B-roll.
- Checklist card (items tick one by one, a tick sound each) and icon stickers over the face (pop sound, placed
  with x/y). Full Lucide icon set (2,437 icons, ISC).
- learn_style.py also studies a video file on the computer, not just a link.
- Speed: full-screen graphics render as opaque video (JPEG capture, H.264), the device mock-up at 15 fps:
  12 graphics in 24 s instead of 260 s.
- Fonts added (OFL): Archivo Black, DM Serif Display, Poppins Light Italic.
- `outro` in plan.json: extra seconds after the last word for an end card (frozen frame + music tail).
- Device screens and stickers accept local images (`img`, `bgimg`, `fit`).

## 1.4.0 - 2026-11-27
- Learned from 6 reference Shorts (references/style-refs.md); `learn_style.py <url>` studies new ones incl. audio.
- Layouts: full-screen cards (`mode: card`) and the rounded face window (`split_style: inset`) on a themed canvas.
- Captions: `duo` style (small words + big italic serif key phrase; never ends on "a/the/to"); dark on cards.
- Graphics: step header (`step: "3/7"`), `comment` CTA card.
- Sound: 12-sound synthesised pack; automatic sound design on every visual beat (`sfx_density`), pre-mixed into
  one track; louder music bed (-14 dB) with gentler ducking for reels; `audio_meter.py` to compare with refs.
- compose retries ffmpeg when it crashes under parallel load.

## 1.3.0 - 2026-11-27
- Auto face framing: face_frame.py finds the speaker's head on 3 frames (MIT BiRefNet-lite) in the background during
  the intake; the bottom panel and zoom-ins are centred on the face. Removes the manual framing fix and its extra render.
- Installer downloads the person model by default (skip with -NoModels); onnxruntime added to requirements.

## 1.2.1 - 2026-11-27
- Retakes: back-to-back doubles always cut ("and and"); 2-word false starts cut only when they break off on a small word
  ("different a | different look"), so lists ("my pauses, my umms") and new sentences are kept.
- Fillers: stretched sounds like "Ohhh", "Ahh", "Hmm" are cut.

## 1.2.0 - 2026-11-27
- Speed: one browser for all graphics, unchanged frames reused (12 graphics in ~17 s instead of 2-4 min).
- Speed: motion backgrounds cached once per look as H.264 (12 MB instead of up to 1.5 GB).
- Speed: final render split into 4 parts rendered at once, audio mixed once, lossless join (~2.5 min instead of 5-9.5 min).
- Retakes: word-for-word second transcription pass on stretched words + automatic retake removal (last take kept).
- Background swap: offered only for green/blue/contrasting plain backgrounds (ffmpeg, ~10 s); recording guide added.
- Diagrams: wide rows shrink to fit the frame; chapter cards can keep normal case (`keepcase`).
- Engineering notes added (references/engineering-notes.md).

## 1.1.0 - 2026-11-27
- Intake: analyse first, A-D looks preview from the user's footage, one question screen (max 4), saved style profile.
- Looks: Clean Paper, Highlighter Yellow, Navy & Gold, Mint Fresh (from a palette study of 10 channels); Dark Glow on request.
- humanizer (blader/humanizer, MIT) is the default for every word the skill writes.
- Matte-assisted background swap (MIT BiRefNet-lite) built, switched off by default.

## 1.0.0 - 2026-11-27
- Combined skill: transcribe, cut, clean voice + background-voice gate, captions (pill/karaoke/minimal),
  graphics (title, diagram, prompt, counter, chapter, lower-third, title3d), motion backgrounds, swipe transitions,
  pixelfx effects, original music + beat sync, colour grade, -14 LUFS, yt-* packaging skills, installer.
- Vendored MIT repos: lemo-opuscar, pixelfx, three.js (npm), mcp-for-blender, ClaudeAnimationBase,
  react-three-rapier, react-postprocessing, awesome-opus5-5-videos; librosa (ISC).
