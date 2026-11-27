# Changelog

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
