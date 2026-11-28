# pro-video-editor

A Claude Code skill that edits talking-head videos into finished reels and YouTube videos. You record on your
phone, give it the file, pick a style on one page, and watch the edit happen. It cuts the pauses, umms and
retakes, cleans your voice, adds captions, graphics, stickers, music and sound effects, grades the colour and
exports a ready-to-post video. If you want to change something by hand, it can open the whole edit in
FilmCraft, a free video editor.

Everything heavy runs on your own computer with free, open-source tools. No API keys, no ChatGPT, no paid
services. Claude Code (your normal Claude plan) is the part that reads your transcript and decides the edit.

![Five steps: drop your video, pick a style, pick captions, watch it edit, edit again](docs/img/flow.png)

![Bold B-roll: hook band, talking with stacked words, a big number per point, glowing comment call-to-action, end card](assets/gallery/storyboard_studio.jpg)

![Clean cards: title card, card above a rounded face window, full card, sticker, recap checklist](assets/gallery/storyboard_mixed.jpg)

![Face and captions: title, big captions, zoom-in, sticker, number card](assets/gallery/storyboard_simple.jpg)

## Contents

- [What you get](#what-you-get)
- [How it works](#how-it-works)
- [The edit page](#the-edit-page)
- [Editing styles and looks](#editing-styles-and-looks)
- [Methods: what happens at each step](#methods-what-happens-at-each-step)
- [Speed](#speed)
- [Install](#install)
- [Use](#use)
- [Optional: touch up in FilmCraft](#optional-touch-up-in-filmcraft)
- [Folder map](#folder-map)
- [Privacy, licences and limits](#privacy-licences-and-limits)

## What you get

- Dead air, filler sounds ("umm", "ahh") and retakes cut out automatically, from word timings.
- Clean voice: noise reduction, background-voice gate, EQ, de-esser, compressor, -14 LUFS loudness.
- Six editing styles learned from successful creators in the AI and side-hustle niche, plus "describe your own".
- Captions in six layouts (word highlight, pill, big serif line, stacked words, minimal, none) and seven colours,
  picked from live samples.
- Tamil, Hindi, Telugu, Kannada, Malayalam, Marathi, Gujarati and more are recognised. The captions come out
  as the English meaning of what you said.
- Cartoon cut-aways with a cast made for each video (skin and shirt colours taken from you), so no two videos
  share the same cartoon.
- Edit the same video again in another style. The earlier finished video is kept.
- Animated graphics: title cards, step cards, diagrams, counters, checklists, prompt boxes, phone and laptop
  mock-ups, big step numbers, icon stickers (2,437 icons), comment call-to-action, end card.
- Original music in six moods, made for each video, lowered automatically under your voice.
- Sound effects on every visual beat (pops, ticks, whooshes), pre-mixed.
- Green screen swap to a moving background.
- A page in your browser where you upload, choose, watch each step and open earlier edits, plus an optional
  hand-editing step in FilmCraft.

## How it works

```mermaid
flowchart LR
    A[You give Claude a video] --> B[Edit page opens on the right]
    A --> C[Analysis in the background<br/>speech to words, cuts, background check]
    B --> D[You pick style, length,<br/>extras, how to finish]
    C --> E[Claude plans the edit<br/>from your transcript]
    D --> E
    E --> F[Graphics rendered<br/>in a headless browser]
    F --> G[Video assembled with ffmpeg<br/>4 parts in parallel]
    G --> H[Finished reel plays on the page]
    H --> I{Touch up?}
    I -->|yes| J[FilmCraft opens with the<br/>edit on its timeline]
    I -->|no| K[Done]
```

1. **You give Claude the video** (drag it in, or type `@` and the path), or drop it on the edit page's start
   screen. Nothing else is needed.
2. **The edit page opens** in Claude's browser pane, and the analysis starts at the same time, so you never wait
   for the first question.
3. **You choose** on the page: a style from the pictures (or describe your own), the length, extras, and whether
   you want to touch it up in FilmCraft afterwards. Press **Start editing**.
4. **Claude plans the edit** from your transcript: which card goes where, what it says (in your own words, run
   through the humanizer so it never sounds AI-written), which stickers pop up when you name something.
5. **The page shows the work live**: graphics appear as they are made, the render percentage climbs, then the
   finished video plays there.
6. **Optional**: FilmCraft opens with everything on a real timeline for hand changes.
7. **Want another look?** Change the style or captions on the same page and press **Edit again with these
   choices**. Your speech is not analysed again, so it is quicker (75 s for a 24 s reel), and the earlier video is
   kept with its style in the file name.

## The edit page

One page for the whole job. It runs on your own computer only (`127.0.0.1`) and opens on the right side of the
Claude app, or in any browser. Faces in these screenshots are blurred and the transcript is hidden.

**Start.** Drop a raw video from your phone or camera (MP4 or MOV, up to 8 GB). It stays on your computer. Your
earlier edits are listed below it; click one to open it again. The **+ New video** button at the top right brings
you back here from any screen.

![Start screen with the upload area and recent edits](docs/img/page_start.png)

**1. Pick a style.** Each picture shows how the style goes from start to finish. Or describe your own look, or
paste a link to a reel you like. Your speech is analysed while you choose.

![The six styles and Describe your own](docs/img/page_styles.png)

**2. Pick captions.** Every layout is shown as a sample subtitle. Pick a colour and the sample changes with it.

![Caption layouts with samples and colour swatches](docs/img/page_captions.png)

**3, 4 and 5. Length, extras and how to finish.** Lengths that don't fit your video are greyed out. Extras are
music, zoom-ins, icon stickers, a recap checklist and cartoon cut-aways.

![Length, extras and finish options](docs/img/page_options.png)

**Watch it work.** Each step shows what it did: words heard, how many gaps were cut, the render progress.

![Progress steps while the edit runs](docs/img/page_editing.png)

**Finished.** The video plays on the page. FilmCraft is there if you want to change something by hand.

![Finished video and FilmCraft panel](docs/img/page_finished.png)

**Edit again.** All the options stay open after an edit, set to what you used. Change any of them and press
**Edit again with these choices**.

![Options kept open with the Edit again button](docs/img/page_edit_again.png)

**Timeline.** The parts of your original that were kept (green) and cut (grey), with cards, stickers, captions
and music. Click anywhere to jump the video there.

![Timeline of kept and cut parts](docs/img/page_timeline.png)

**Graphics.** Each graphic shows up the moment it is rendered:

![Graphics appearing as they are made](docs/img/page_graphics.png)

**Remove an edit.** The x on a recent edit removes it from the list. Tick the box to also move its working files
to the Recycle Bin. Your original video and the finished video are never deleted.

![Remove dialog](docs/img/page_remove.png)

## Editing styles and looks

| Style | What it looks like | Best for |
|---|---|---|
| **Bold B-roll** | Hook title band over B-roll, warm cinematic face, a big lime number over a phone or laptop shot for every point, stacked-word captions, glowing "Comment X", end card | Lists and "N steps" videos |
| **Clean cards** | Cards above your face in a rounded window, full-screen cards, serif key-word captions, step headers | Explainers and how-tos |
| **Face and captions** | Your face the whole time, zoom-ins, word-highlight captions, a title and a few cards | Opinions and stories; fastest |
| **Bold + Animated** | Bold B-roll with an animated cartoon scene for every point | Stories and lists that need more movement |
| **AI News** | You over the headline: screenshots zoom in, key lines highlighted | Reacting to news and launches |
| **Screen tutorial** | Your screen recording zooms to each click, your face in a bubble | Showing how to use a tool |
| **Describe your own** | Claude picks the nearest style and applies what you wrote (or studies a reel you link) | Anything else |

The storyboards at the top of this page show each style from start to finish, and the edit page uses the same
pictures in its style picker. The presenter in them is AI-generated, not a real person.

Colour looks for Clean cards and Face and captions:

![Colour looks](assets/gallery/looks.jpg)

If a storyboard is missing, the picker falls back to the illustrated gallery made by `scripts/make_gallery.py`
(a presenter drawn in code, rebuilt whenever a template changes).

## Methods: what happens at each step

**Speech to words** (`scripts/transcribe.py`). faster-whisper "small" (int8) on the CPU gives every word with a
start and end time. A second, word-for-word pass re-listens to stretched words, because Whisper tidies speech
and would otherwise hide repeated words.

**Cutting** (`scripts/cut.py`).
- Pauses: gaps between words, plus ffmpeg `silencedetect` set 2 dB under your average voice level.
- Words are protected: a quiet word is never removed as "silence", and a slowly spoken word keeps at least
  0.4 s (only the dead air inside it is trimmed).
- Fillers: "umm", "uh", stretched "ohhh/ahh/hmm".
- Retakes: a restart within 12 s that matches 60% of the words just said is cut; back-to-back doubles
  ("and and") are always cut; common phrases like "step by step" are kept.

**Analysis** (`scripts/analyze.py`). Picks a starting preset from the video's shape and topic, checks loudness and
noise, and checks the background: a real or digital green screen, or a plain wall far from skin and clothes
colours, can be swapped.

**Face framing** (`scripts/face_frame.py`). A small person-segmentation model (BiRefNet-lite, MIT) finds your head on
three frames while you are choosing, so crops and zoom-ins stay centred on your face.

**Graphics** (`templates/gfx.html`, `scripts/render_gfx.mjs`). Each graphic is an HTML page animated frame by frame in
one headless Chromium (Playwright). Frames that do not change are reused. Full-screen graphics are captured as
JPEG into H.264, transparent ones as PNG into QuickTime Animation. Fonts are Poppins, Instrument Serif,
Archivo Black and DM Serif Display (all OFL); icons are Lucide (ISC).

**Captions** (`scripts/captions.py`). Written as an ASS subtitle file and burned in with libass. Groups never end on
small words like "a" or "the"; on light cards the small words turn dark so they stay readable.

**Assembly** (`scripts/compose.py`). One ffmpeg filter graph per part, four parts rendered at the same time and joined
without re-encoding.
- Crop and colour grade at the source resolution, then one upscale (phone footage is often 576x1024).
- Zoom-ins: the same crop shrinks at the zoom moments (ffmpeg `sendcmd`), so there is no second zoomed copy.
- Layouts: face only, card above a rounded face window on a moving page background, full-screen cards.
- Green screen: a tight colour key for flat digital screens, a chroma key for real ones, then despill and a
  2-pixel edge pull so no green fringe stays on hair.
- Encoding: x264 veryfast, CRF 18.

**Sound** (`scripts/sfx_design.py`, `scripts/music.py`). Sound effects are placed from the plan (a tick per checklist
item, a pop per sticker, a whoosh per card) and mixed into one track. Music is composed by the script in the
chosen mood, levelled, ducked under your voice with a sidechain compressor, and faded. The voice chain is
noise reduction, a speech gate built from the word timings, EQ, de-esser and a compressor. The master is
-14 LUFS with a limiter.

**Live page** (`scripts/live.py`, `scripts/livelog.py`, `templates/live.html`). A small standard-library web server on
127.0.0.1. Each step writes a short note to `live.json`, the page polls it every second, and render progress is
read from ffmpeg's `-progress` files. Your choice is sent back as `choice.json`, protected by a one-time page
token so no other website can post to it.

**FilmCraft bridge** (`scripts/filmcraft_open.py`). Drives FilmCraft through its documented JSON control channel with a
fresh random token kept only in memory: imports the original video and graphics (converted to ProRes 4444
with transparency), places the kept parts, cards, stickers, captions and music, and saves a `.fcproj`.

## Speed

Measured on a 4-core laptop with no NVIDIA graphics card, for a 1-minute phone reel:

| Step | Time |
|---|---|
| Listening and cutting | about 1 min, while you choose your style |
| Graphics | 20 s to 3 min, depending on how many |
| Assembling the video | about 2 min (was 3 min 43 s before the speed work) |
| FilmCraft hand-off (optional) | about 1 min |

How the assembly got 44% faster at the same quality (checked with SSIM against a near-lossless reference):
grading at source resolution (effects 54.6 s to 20.5 s per part), zoom-ins as one timed crop, and x264
veryfast at CRF 18 (SSIM 0.98753 vs 0.98765 for the old setting). Details in
[references/engineering-notes.md](references/engineering-notes.md).

## Install

Windows, with Python 3.10 to 3.12 from python.org, Node.js LTS and ffmpeg:

```powershell
winget install Gyan.FFmpeg
```

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

The first install takes 5 to 10 minutes: it creates a Python environment, installs the headless browser and
downloads the Whisper speech model (about 480 MB), the person model (224 MB) and the big speech model for Indian
and other languages (large-v3-turbo, MIT, 1.6 GB).

| Option | What it adds |
|---|---|
| `-WithFilmCraft` | FilmCraft for hand touch-ups (free, MIT or Apache-2.0, about 115 MB, checksum verified) |
| `-WithRNNoise` | Neural voice noise models (no explicit licence, so opt-in) |
| `-NoModels` | Skips the model downloads |
| `-NoBigSpeech` | Skips the 1.6 GB speech model (English still works; other languages come out wrong) |
| `-AllowNonMIT` | Extra libraries that are not MIT or ISC (off by default) |

If Windows Smart App Control briefly blocks a new library, the installer waits and tries again. It never turns
any protection off.

## Use

In Claude Code, from any folder:

- "Open the edit page": the start screen opens and you drop your video there.
- `@"D:\clips\my-reel.mp4"` and nothing else: the edit page opens and you choose there.
- "Edit this into a 30 s reel with yellow captions and no music": the description is used as your style.
- "Swap the green background": works when the background can be keyed.
- "Change the music to cinematic", "make the captions bigger": Claude edits the plan and re-renders.

Command line without Claude (cuts, voice, captions, colour, zoom-ins and music, but no cards or stickers,
because those need judgement):

```powershell
.venv\Scripts\python.exe scripts\autoedit.py "my video.mp4"
```

The edit page on its own, without Claude (choices made on the page run the automatic edit):

```powershell
.venv\Scripts\python.exe scripts\live.py --home "D:\clips" --open
```

## Optional: touch up in FilmCraft

Choose **Done for me + touch up in FilmCraft** on the edit page, or press **Open in FilmCraft** after any edit.
FilmCraft opens as its own window with:

| Track | Contents |
|---|---|
| V1 / A1 | your original video in its kept parts, so every cut can be adjusted |
| V2 | page-colour background under full-screen cards |
| V3 | cards |
| V4 | stickers, at the same positions as in the reel |
| C1 | captions |
| A2 | music at the reel's level |

FilmCraft does not reproduce the skill's caption styles or the card-and-face-window layout, so the reel from the
skill stays the final file. FilmCraft is best for trying changes (for example a different music track) by hand.

## Folder map

```
SKILL.md                  instructions Claude follows (the workflow above)
install.ps1               installer
scripts/                  autoedit, transcribe, cut, analyze, compose, captions, render_gfx, live, filmcraft_open,
                          music, sfx_design, make_gallery, learn_style (study a reference reel), and more
templates/                gfx.html (all graphics), live.html (edit page), motionbg.html, title3d.html
styles/                   edit_styles.json (the six styles), presets.json, themes.json (colour looks)
assets/                   fonts, icons, sound effects, gallery pictures
references/               style notes learned from reference videos, engineering notes, recording guide
skills/                   humanizer and YouTube helpers (chapters, titles, SEO, Shorts)
vendor/                   vendored MIT libraries (see LICENSES.md)
docs/img/                 the screenshots in this README
```

## Privacy, licences and limits

- **Your videos stay on your computer.** Only the transcript text and the still frames Claude checks go to Claude,
  as with anything in Claude Code. The live page and FilmCraft listen on 127.0.0.1 only. This repository never
  contains videos, audio or edit folders (see `.gitignore`).
- **Licences:** everything bundled is MIT, ISC or OFL; anything else is opt-in. See [LICENSES.md](LICENSES.md).
- **Limits:**
  - Whisper can mishear names, so Claude checks the transcript.
  - Speech in Tamil and other Indian languages becomes English-meaning captions, not captions in your own
    script, and the word highlight does not match each spoken word exactly.
  - Background voices talking over you cannot be separated.
  - Background swap needs a green or blue screen or a plain wall far from your skin and clothes colours.
  - WhatsApp lowers video quality, so send the original file by cable or Drive.
