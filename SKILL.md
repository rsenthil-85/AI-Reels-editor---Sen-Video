---
name: pro-video-editor
description: >-
  Professional video editing of the user's own footage, end to end: jump cuts, clean voice (noise and
  background-voice removal), auto-chosen or user-described style, captions, motion graphics (2D and 3D titles,
  diagrams, prompt boxes, counters, lower-thirds, chapter cards), B-roll and screenshot inserts, face bubble
  over screen recordings, original music with ducking, beat-synced montages, colour grade, -14 LUFS master,
  plus titles/chapters/SEO/Shorts. Use for "edit my video", "make this reel look pro", "clean my audio",
  "remove background noise", "cut this long video", "add captions/graphics/music", "make a montage to music",
  or whenever the user gives a video file and wants a finished edit - with or without describing the style.
---

# pro-video-editor

Version 1.12.0 - see CHANGELOG.md. How it works, what was measured and why: `references/engineering-notes.md`
(read it before changing the pipeline). Recording advice for users: `references/recording-guide.md`.

Every video goes: **gallery + style question (instant, analysis runs behind it) -> short brief -> edit -> stills -> final**.

`PY` = `<this skill>/.venv/Scripts/python.exe` (made by install.ps1). `S` = `<this skill>/scripts`.
If `.venv` is missing, tell the user to run `install.ps1`; never install interpreters yourself and never
disable or work around Windows security prompts.

## 0. The moment a video arrives: ONE edit page (choose, watch, touch up)

Everything happens on one page in the browser pane on the right (templates/live.html served by scripts/live.py):
the user picks the style there, watches the edit, and can finish in FilmCraft from the same page.

1. Start, all in the background (Bash `run_in_background`), in this order:
   - `PY S/live.py <video> --port 8765` (it takes the next free port if busy: read the port from its first line), then
     open the page in a NEW browser tab for every new video (tabs_create foreground, then navigate that tab) - never reuse
     an old video's tab - and SHOW the pane (show_pane "preview"; a hidden pane is invisible to the user). Close tabs of
     finished edits when asked. No browser pane (other agents): add `--open` to open it in the normal browser.
   - `PY S/autoedit.py <video> --analyze`
   - the hand-off wait: `PY S/wait_choice.py --timeout 3600` (prints `{"video","edit_dir","choice"}` and marks the
     choice taken). While it runs it tells the page an agent is listening; without it the page runs the automatic
     edit itself (no hand-made graphics). No video yet? `PY S/live.py --home <folder>` shows the start screen: the
     user drops a raw video in the browser, and "+ New video" (top right) or Recent edits switch videos; run
     wait_choice.py again after each finished edit to catch the next one.
2. Tell the user in one or two lines: "Pick your style on the right and press Start editing - it's analysing your
   video meanwhile." The page shows the gallery pictures (assets/gallery/style_*.jpg), "Describe your own", length
   (full / 60 / 30, only what fits), extras (music, zoom-ins, icon stickers, recap checklist) and how to finish:
   **Done for me** or **Done for me + touch up in FilmCraft** (only enabled when FilmCraft is installed).
   If the user answers in the chat instead, write the same choice.json yourself and carry on.
3. When the wait finishes, read choice.json and map it: style -> answers.json `style` ("describe": nearest style +
   the user's words as overrides, see section 3); length full/60/30 -> format reel_full/reel_60/reel_30; extras
   music/zooms -> extras; `captions` (karaoke|pill|duo|stack|minimal|none, "style" = the style default) and
   `caption_color` (#RRGGBB) go into answers.json as they are; stickers/checklist -> you add `sticker` overlays / a `checklist` card; always include
   "graphics". Look: the user's last profile, else Clean Paper. Then section 3 (edit) and section 4 (render).
4. finish = "filmcraft": after compose.py finishes, run `PY S/filmcraft_open.py <video>` (background). The page shows
   FilmCraft's progress and a picture of its window next to our video; FilmCraft itself opens as a desktop window
   with the edit on its timeline. The page also has an "Open in FilmCraft" button after any finished edit.
Tell the user where to look; do not repeat the page's content in the chat.
If a template or style changes, re-run `PY S/make_gallery.py` (about 5 s) so the gallery matches what the skill makes.
Fallback without a browser pane: the inline picker (show_widget: style tiles with small SVG mock-ups + Describe
your own + length + extras), never style names alone; AskUserQuestion hides the chat, so never rely on an image sent
just before it.

## Live edit page (on by default): the user watches the edit happen

Right after the video arrives, start the page and open it on the right, before asking anything:
```
PY S/live.py <video> --port 8765          (Bash, run_in_background - local only, read-only, stdlib)
```
then open `http://127.0.0.1:8765/` in the browser pane (preview_start with that url; if the first navigation is
refused, navigate again once the server has printed its line), then make sure the user can SEE it: the pane is
often hidden - check tabs_context and show it (show_pane "preview"); a page in a hidden pane is invisible to them. Any browser works too. The page polls
`<name>_edit/live.json` (written by scripts/livelog.py from autoedit, transcribe and compose) and shows: the steps
with live details (heard 40% of your video / 78 s down to 55 s / 9 of 15 graphics / rendering 63%), the cut video
(then the finished one), a clickable timeline (original kept vs cut, cards, stickers, captions, zoom-ins, music),
each graphic the moment it is rendered, and the transcript with the cut words struck out. Tell the user in one line
that it is open. If port 8765 is busy use another. Stop the server task when the job is delivered.

## 1. Analyse (runs in the background from step 0)

```
PY S/autoedit.py <video> --analyze [--drop "a-b,..."]
PY S/looks_preview.py <name>_edit            # optional: A-D colour looks on THEIR footage (~10-60 s)
```
Transcribe (cached), analyse, cut dead air/fillers. Read `transcript.srt` and find retakes/flubs ("sorry",
restarted sentences, "you know, like"); re-run `--analyze --drop` with source times. Never guess - for long
videos list them for the user first. Read `intake.json` (recommended answers, `last_profile`) and LOOK at
`sheet.jpg`. If the analysis recommends a different style from the one picked, keep the user's pick.

## 2. Intake: ask the brief (AskUserQuestion: the editing style first, then max 4 questions)

Rules:
- **Style first, on its own** (one AskUserQuestion call, right after sending `assets/gallery/styles.jpg`; the
  options are labelled A/B/C like the gallery): which editing style - options from `styles/edit_styles.json`
  (`styles/edit_styles.json`), recommended first: **Clean cards** (mixed: face / card + face window / full cards),
  **Bold B-roll** (studio, ref 7: hook title band, warm face, full-screen B-roll with big numbers per point,
  stacked-word captions, glowing comment CTA, end card), **Face and captions** (simple). The style decides the
  layout, caption style, grade and graphics; the next screen only asks what is left.
- Then (send `assets/gallery/looks.jpg` when the Look question is asked) ask the rest in ONE AskUserQuestion call. For Bold B-roll skip the
  Look question (it has its own black, lime and warm colours).
- Put the recommended option first with "(Recommended)" - from `intake.json`, based on this video.
- Skip any question the user's message already answered. If they said "just edit it" / "you choose", skip
  the whole brief and use `recommended`.
- If `last_profile` exists, ask only one question first: "Same style as last time?" (Yes / Change it).
- Never ask about the always-on items: dead-air and filler cuts, clean voice and background-voice gate,
  colour grade, loudness, humanizer wording.
- No host question tool? Ask the same questions as a numbered text list and accept "1b, 2a, 3: a c d".

The questions (header, multiSelect):
1. **Format** (single) - Reel, full length (cut) / Reel, about 60 s / Reel, about 30 s / Long-form YouTube.
   Offer only what fits: a 40 s video gets no 60 s option. Say the cut length in the question.
2. **Look** (single) - A Clean Paper / B Highlighter Yellow / C Navy & Gold / D Mint Fresh, each with its
   `looks_like` in the description, matching `looks.jpg`. Dark Glow only if the user asks for it.
3. **Captions** (single) - the style's own caption first (Clean cards: serif key words `duo`; Bold B-roll: stacked
   words `stack`; Face and captions: word highlight `karaoke`), then Word highlight / Pill / No captions.
   Ask it only when another question was skipped; otherwise leave it out (captions follow the style).
4. **Extras** (multiSelect: true) - Motion background / Step graphics and diagrams / Zoom-ins / Swipe transitions.
   **Background swap** (`styles/features.json` background_swap = "keyable_only"): offer it ONLY when
   `intake.json` background.keyable is true (green/blue screen, or a plain wall far from skin and clothes).
   Then make the first Extras option **Animated background behind you** (extras `bg_replace`, ffmpeg key,
   ~10 s extra) and drop Swipe transitions to keep 4 options. If not keyable: don't offer it, edit as normal,
   and after delivery give the short version from `references/recording-guide.md` (green or blue cloth or
   wall, 1 metre in front, even light, no cream/beige/wood). The slow AI matte for other walls
   (scripts/matte.py, ~11-20 min per minute) runs only when background_swap = "all" or the user asks for it.
   (+ the user can type more under Other: background music mood, celebration effects, my own B-roll at <path>).
   Music is on by default with the preset's mood; if the user types a mood, use it; "no music" turns it off.

Map answers to `answers.json` (schema at the top of autoedit.py): style mixed|studio|simple, format reel_full|reel_60|reel_30|long,
look paper|highlight|navy|mint, captions karaoke|pill|minimal|duo|stack|none (leave out = the style's own), extras motion_bg|graphics|zooms|
transitions|music|effects|broll, music_mood. Keep "music" in extras unless they said no music.

## 3. Edit

**Described style** (the user wrote their own instead of picking a tile): choose the nearest style in
`styles/edit_styles.json` as the base (`style` in answers.json), then apply what they asked on top in plan.json:
caption_style (pill/bold/minimal/duo/stack), accent and theme, grade (true/"warm"), music mood, layout pieces
(full cards, inset window, B-roll + bignum, stickers), pace. A link to a reel: study it first with learn_style.py.
Say back in one line what you understood ("Bold B-roll base, yellow pill captions, no music") before rendering.

```
PY S/autoedit.py <video> --answers <name>_edit/answers.json --no-render
```
Writes plan.json from the answers (and saves them as the user's profile). Then do the `_todo` items in
plan.json by hand:
- `graphics`: add inserts following the preset's `graphics`/`layout` and `references/`. Reels: something
  changes every 2-4 s. Long: a visual change at least every ~8 s. All text through humanizer (below).
- `effects`: 1-3 pixelfx overlays on real high points (a number, the CTA), never across text.
- `broll`: insert the user's clips/screenshots where the transcript mentions them.
- `trim to ~Ns`: choose the strongest spans (skills/yt-shorts), re-run `--analyze --drop`, then `--answers` again.
Fix misheard names with `"fix"` in plan.json (read `words_cut.json`).

## 4. Render, check, deliver (fast path)

`PY S/compose.py <name>_edit/plan.json` - no separate preview pass. It renders graphics in one browser
(still frames reused), splits the timeline into 4 parts rendered at the same time, mixes audio once, and
joins the parts without re-encoding (same encoder settings, so quality is identical). Then pull stills at
every insert/overlay and LOOK. If something needs fixing, edit plan.json and run compose again: unchanged
graphics are cached, so a fix costs about one render pass. `--single` forces the old one-pass render
(debugging); `--preview` makes a quick 540p check. Report: file path, what was cut, what was added, what
was not verified. End with **ship it, or change it?**

## Mixed layouts, captions and sound (learned from reference Shorts - see references/style-refs.md)

- Layout mix: face only / card + face (`"split_style": "inset"` = rounded face window on the canvas) /
  full-screen card (insert `"mode": "card"`). For explainers and how-tos aim ~30-40% / 30-40% / 20-30%.
- Captions `"caption_style": "duo"`: small plain words + key phrase on its own line in big italic serif accent;
  on full-screen cards they move low and turn dark (`ink`).
- Card extras: `"step": "3/7"` on any graphic (STEP header, progress dots, big faded number); type `comment`
  ({"word": "MAGGI", "l2": "..."}) for the comment CTA.
- Sound design is automatic (scripts/sfx_design.py): `"sfx_density": "low|medium|high"` (reels default high:
  swoosh per card change, pop per diagram item, count-up ticks + ding, typing under prompts, tick on step
  headers, thump on full cards and punch-ins, soft click on caption lines). Music bed `music_db` -14 with
  gentle ducking (`duck_ratio` 4) for reels. Check with `scripts/audio_meter.py out.mp4 words_cut.json`
  (references: bed ~3-6 dB under voice peaks, 7-76 SFX hits/min).
- New reference from the user: `scripts/learn_style.py <url>` -> contact sheet, cuts, captions, audio stats;
  write the findings into references/style-refs.md, then build what is missing.

## Cartoon scenes (`type: toon`) and the Bold + Animated style (animated)

Animated cut-aways in Lemo-Opuscar's Mid-century cartoon style (engine bundled in `templates/toon/`, MIT), rendered by
the normal graphics renderer (`templates/toon.html`, 24 fps, opaque): about 5 s of work per 4 s scene. Our own
creator and robot; five scenes, picked by what the speaker is saying:

| scene | use it when the speaker... | labels |
|---|---|---|
| `struggle` | describes the problem, the time or effort it used to take | `l1` tag on the clock ("2 hours") |
| `relief` | introduces the fix ("so I built...", "AI does it") | `l1` optional tag |
| `machine` | explains how something works (input -> process -> result) | `l1` input, `l2` output |
| `beforeafter` | compares two states | `l1` before, `l2` after |
| `checklist` | lists steps or features | `l1` heading, `items` "a|b|c" (max 5) |

Insert: `{"t0","t1","mode":"full","gfx":{"type":"toon","scene":"struggle","l1":"2 hours"}}` (dur comes from t1-t0); in a
top panel use `"mode":"top"`. The extra **Cartoon cut-aways** on the edit page adds 1-3 of them to any style.

**Every video gets its own cast** (never the same cartoon twice): before rendering, look at `sheet.jpg` and run
`PY S/toon_cast.py <name>_edit --hair side|short|curly|spiky|bald|bun|long --beard none|stubble|full|moustache [--glasses]`.
It samples the speaker's skin tone and shirt colour from the video (face.json position), and picks the robot (colour,
head shape, antenna), the room palette (5 sets), two pieces of wall decor and the prop colour from a seed made from the
video's name, so the same video re-renders the same and every new video looks different. compose.py passes
`toon_cast.json` to every toon graphic (and runs toon_cast.py itself if you forgot, without the hair/beard you saw).

**Bold + Animated** = Bold B-roll with a cartoon scene for every point: hook = a toon scene in the top panel + the band
overlay; face with stacked captions and zoom-ins; each listed point = a full toon scene + `bignum`; `ctaword` on the
comment line; `endcard` outro. **Animation look:** Mid-century cartoon by default. If the user links a reference (or
asks for anime, whiteboard, crayon, rubber hose, watercolour...), study it (learn_style.py) and pick the closest of
Lemo's 66 styles (`~/lemo-opuscar/AGENTS.md` lists them). Only midcentury-toon is bundled as ready scenes; another style
means directing those scenes as a short Lemo film (lemo-opuscar skill: treatment, the style's engine from
`setup.sh demo <slug>` - on Windows extract it with `git archive`, the script mangles paths - our own characters, never
the demo's), rendered with `node core/render/video.mjs <project> --size 1080x1920 --fps 24` (~2 s of render per 1 s of
film), then inserted with `"src"`. Say which look you picked and why in one line.

## AI News style (news) - how to build it
Needs screenshots (choice.json `materials`: uploaded on the page into `<name>_edit/materials/`, file paths, a folder, or
links to screenshot with the headless browser). Your face full frame with
`{"type":"badge","text":"New"}` for 2-3 s, then for each screenshot an insert `mode: bubble` with
`{"type":"shot","img":"<path>","focus":"x,y,w,h"}` (the key line as fractions of the image: LOOK at the screenshot to
find it; `tz` = when the zoom starts) for as long as the speaker talks about it; opinion on the face; comment card.
The bubble is cropped around the face (auto face framing). Green screen: add the swap, it also shows in the bubble.

## Screen tutorial style (tutorial) - how to build it
Screen recording is optional (choice.json `materials`: a file uploaded on the page, saved in `<name>_edit/materials/`,
a pasted file path, or a video link). A link: download it with `PY -m yt_dlp -o "<name>_edit/materials/screen.%(ext)s" <url>`
(the user's own video; say so if the site refuses). Nothing given: build the screen with graphics instead - inserts
`mode: bubble` with `{"type":"device","kind":"laptop", "head":..., "rows":..., "cursor":1}` and `{"type":"prompt"}` (types
the prompt the speaker reads out) at each step, same badges. With a recording, run
`PY S/screen_zoom.py <screen.mp4> <name>_edit/screen_vertical.mp4 --top 0.04 --area 0.58` (finds clicks / typing by
comparing frames, holds a zoom on that area; ~10 s for 20 s), then an insert `mode: bubble` with
`"src": "screen_vertical.mp4"` and `"ss"` to line it up with what is said. Badges
`{"type":"badge","text":"Step 1 of 3: ...","tone":"blue","dot":"0"}` at each step; intro and result on the face.
Captions sit at 0.655 between the screen and the bubble.

## Bold B-roll style (studio) - how to build it (ref 7, references/style-refs.md)

plan.json from `--answers` already has `layout: studio`, `grade: "warm"`, `caption_style: "stack"`, lime accent,
`sfx_density: medium`; `_style_graphics` says what to add. Build it like this:
- **0-4 s hook**: insert `mode: top` with the user's B-roll/screenshot (or a `device` mock-up) + overlay
  `{"type":"band","l1":"<money line>","l2":"<italic second line>","y":0.45}` for the same span. Face below.
- **Face full frame** for talk; zoom-ins on.
- **Each listed point** ("first / second / step 1"): insert `mode: full` with real B-roll (user clips or screenshots,
  `kb: true` for stills) for 2.5-5 s, else `{"type":"device","kind":"phone|tablet|laptop","head","sub","label",
  "value","rows":"A:x|B:y","cursor":1}` (or `"img":"screenshot.png"`), plus overlay `{"type":"bignum","n":"1"}`
  over the same span. The device moves right and up by itself to make room for the number and the captions.
- **Things named while on the face**: `sticker` overlays (any of the 2,437 Lucide icons in assets/icons, + label).
- **Recap**: a full `checklist` card (`bg` set) ticking the points.
- **CTA**: overlay `{"type":"ctaword","word":"<keyword>"}` on the "comment X" line (riser + stamp sound).
- **End**: `"outro": {"dur": 3, "gfx": {"type":"endcard","lines":"a|b|c","hl":2,"icon":"message-circle"}}` adds
  3 s after the last word (frozen frame, music runs on, the card covers it). Never use another company's logo (WhatsApp, YouTube...): a plain icon, and the name in the text.
Full-screen graphics of this style render as opaque video (device at 15 fps): about 2 s each.

## Optional: open the edit in FilmCraft (hand tweaks on a real timeline)

After delivering, if FilmCraft is installed (`install.ps1 -WithFilmCraft`, or ~/.pro-video-editor/filmcraft.json exists),
offer one button: "Open in FilmCraft to adjust by hand". On yes:
```
PY S/filmcraft_open.py <video>          (~15-40 s; FilmCraft opens as its own desktop window)
```
It builds the edit live on FilmCraft's timeline: the original cut into its kept parts (V1/A1, scaled to fill the frame,
phone rotation handled), a page-colour matte under full cards (V2), our graphics as ProRes 4444 (V3, placed like
compose places them), stickers at their x/y (V4), captions (C1, Poppins), music at music_db (A2), and saves
`<name>_edit/filmcraft/<name>.fcproj`. Tell the user: it is for hand changes and review; FilmCraft does not reproduce
our caption styles (duo/stack/karaoke) or the card + face-window layout, so the reel from compose.py stays the final file.
Not installed? Say it is an optional free app (MIT or Apache-2.0, ~115 MB) and ask before running the installer switch.
Never disable Windows security for it; if Smart App Control blocks it, wait and retry.

## Wording sounds human (default, always on)

Every word this skill writes goes through `skills/humanizer/SKILL.md` (blader/humanizer, MIT) in embedded mode
before it reaches the user or the screen: on-screen text, titles, prompt boxes, CTAs, chapter names, video
titles, descriptions, hooks, scripts and voice-over lines. Read it once per job.
- The writing sample is the speaker's own transcript (`transcript.srt`): match their words, sentence length
  and phrasing. Prefer a phrase they actually said over a new slogan.
- Spoken voice-over extras: contractions, sentences under ~15 words, one idea per sentence, read it aloud in
  your head; no em dashes, no "unlock / game-changer / dive in / let's explore", no triads for rhythm,
  no one-line "That's the secret." closers.
- On-screen text: 2-5 plain words, sentence or title case, no emojis or arrows as decoration.
- Never change facts, names, numbers or prices while rewriting.

## Clean voice (on by default)

- `voice_clean`: RNNoise neural denoise if `assets/rnnoise/*.rnnn` exists (install -WithRNNoise), else strong
  FFT denoise; then de-mud (-3 dB @250 Hz), presence (+3 dB @3.5 kHz), de-ess, compressor.
- `speech_gate` (default on when there is speech): a gain envelope built from the speaker's word timings
  mutes everything between their words to `speech_gate_floor` (0.12) - removes background voices, TV,
  street noise and breaths in the gaps. Voices talking OVER the speaker cannot be separated; say so.
- Loudness: -14 LUFS integrated, true peak <= -1.3 dB (loudnorm + limiter).

## Plan reference (compose.py)

Top of `compose.py` has the full schema. Key fields: `format` reel|long, `inserts` (mode top|full|bubble,
`gfx` or `src` file, `sfx`), `overlays` (transparent gfx), `punch` auto|list, `captions`, `caption_style`
pill|bold|minimal, `caption_y`, `accent`, `emph`, `fix`, `music` (path | `auto:<mood>`), `music_db`,
`voice_clean`, `speech_gate`, `grade`, `sharpen` (0-1, for soft/WhatsApp footage), `preset` (x264, default faster).

Graphics types (`gfx`): title (l1/money/l2), chapter (label/word/center), lower (name/role/photo),
counter (value/caption), prompt (head/tool/text - types itself), diagram (head/items/icons/op/result/ricon),
**title3d** (l1/big/l2 - three.js scene with bloom, opaque dark background), checklist (head/items/icons/subs/result/layout),
sticker (icon or img/label/color - small tile, positioned with x/y), band, bignum, ctaword, endcard, device (Bold B-roll). All take `acc`, `k` (scale).

Pro polish (v3, on for reels): `"panel_bg": "auto:aurora|grid|bokeh"` - looping three.js shader background
behind split-stack graphics (templates/motionbg.html); `"transitions": true` (default) - accent swipe over the
top panel at every content change, plus an accent seam line; pixel-art VFX overlays from pixelfx:
`{"t": 45.7, "pfx": "ui/confetti", "x": 0.5, "y": 0.38, "w": 760, "sfx": "pop"}` (scripts/pixelfx.py; good ones:
ui/confetti, explosions/firework-burst, arcane/star-fall, spawn/coin-drop, pickups/collect-burst). Keep effects
off text: place them at panel edges or the seam, never across a headline. A full-screen `title3d` insert
(`mode: full`, 1.5 s, sfx riser) on a key line ("remember one thing") is a strong pattern break.

## Music and beat sync

- `music.py out.wav --seconds N --mood lofi|chill|upbeat|corporate|tech|cinematic` - original track, no licences,
  writes `.beats.json`. compose.py does this itself for `"music": "auto:<mood>"`.
- User's own track: `beats.py song.mp3` (librosa) -> beats/bars.
- No speech / B-roll only: `montage.py clips_dir music.wav out.mp4 --every bar` cuts a shot on every bar.

## Optional heavy steps (ask first - they are slow on a laptop CPU)

- `upscale.py` - Real-ESRGAN x4 (needs a torch env and the model file, BSD-3; not bundled). ~2.4 s/frame with
  `--half` on an i7 laptop: a 1-min reel ≈ 70 min. Intel iGPU gives wrong output for this model - CPU only.

## Built-in skills (skills/)

yt-script (hooks), yt-shorts (pick clips from long videos), yt-chapters, yt-package (title+thumbnail),
yt-seo, yt-viral (what works in a niche), yt-edit (dead-air report), yt-retention. Use them after the edit
for long-form packaging or before recording for hooks.

## Vendored libraries (vendor/) - when to reach for them

See `references/vendor-guide.md`. In short: **lemo-opuscar** for whole animated films/explainers in 99
styles; **pixelfx** for pixel-art VFX overlays (sprite sheets -> overlays); **three.js** (installed) for 3D titles
and scenes; **mcp-for-blender** when the user has Blender and wants 3D product shots; **ClaudeAnimationBase**
for hand-painted character animation (needs p5: LGPL, opt-in); **react-three-rapier / react-postprocessing**
are reference only unless installed with -AllowNonMIT; **awesome-opus5-5-videos** is a prompt library for
motion-graphics ideas - read prompts, write your own code.

## Limits

- Whisper mishears names - always proof `words_cut.json`.
- Other languages: transcribe.py detects the language. Tamil, Hindi, Telugu and the rest use large-v3-turbo
  (MIT, ~1.6 GB, downloaded once with the user's OK, never bundled) and come out as the English meaning, not native
  script (37 s Tamil clip: 90 s). The page says so. Without the big model it warns that captions may be wrong.
- Auto face framing: `--analyze` starts scripts/face_frame.py in the background (MIT BiRefNet on 3 frames, ~40 s,
  during the questions); `--answers` puts face_x/face_y into plan.json. One position per video (not tracking):
  still glance at a still of the bottom panel. Without the model it falls back to 0.5 / 0.45.
- Background voices overlapping the speaker stay. Recording advice: quiet room, clip-on mic, record on the
  phone and transfer by cable/Drive, not WhatsApp (WhatsApp drops resolution to ~576x1024).

## The gate

Nothing here publishes. Hand back the file path and stills; the last line is always **ship it, or change it?**
