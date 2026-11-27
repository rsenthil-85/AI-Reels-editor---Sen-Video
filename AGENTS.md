# AGENTS.md - read this first

This file is for any AI coding agent working in this folder: Claude Code, Codex / ChatGPT, Gemini (Antigravity,
Gemini CLI), Cursor, Copilot, Windsurf, Aider, or a local model. It says what we are building, how the pieces fit,
how to run and test them, and the rules. `SKILL.md` is the step-by-step workflow Claude Code follows when it edits
a video; this file is the map for anyone changing or extending the code.

## What this is

**pro-video-editor**: an AI video editor for talking-head reels and YouTube videos in the AI / side-hustle niche.
A creator records on a phone, gives the file to an agent, picks a style on a local web page, and gets a finished,
professional reel: pauses and retakes cut, clean voice, captions, animated graphics, stickers, music, sound
effects, colour grade, -14 LUFS, optional green-screen swap, optional hand touch-up in FilmCraft.

Goals, in order:
1. **Quality like a pro editor**, matching the reference styles in `references/style-refs.md`.
2. **Runs on a normal laptop, free and local.** No paid APIs, no API keys, no cloud rendering. Measured on a 4-core
   Windows laptop with Intel UHD 620 and no NVIDIA GPU.
3. **Fast**: about 6 minutes from upload to finished 1-minute reel for a first-time user. Never trade quality for
   speed without measuring (SSIM) and saying so.
4. **Simple for the creator**: one page (style pictures, length, extras, how to finish), live progress.

## How it works (pipeline)

```
video ──► transcribe.py ──► analyze.py ──► cut.py ──► (choice from the edit page) ──► plan.json
           words+times       preset,          cut.mp4,          choice.json              │
                             background       segments.json                             ▼
                                                                    render_gfx.mjs (graphics) + compose.py (ffmpeg)
                                                                                            │
                                                                       finished .mp4 ──► filmcraft_open.py (optional)
live.py serves templates/live.html the whole time; every step writes progress through livelog.py
```

| Step | File | What it does |
|---|---|---|
| Orchestrator | `scripts/autoedit.py` | `--analyze`: transcribe, analyse, cut, write `intake.json`, start face framing. `--answers answers.json`: turn the user's choice into `plan.json`. |
| Speech to words | `scripts/transcribe.py` | faster-whisper small int8 on CPU; second word-for-word pass on stretched words to recover hidden repeats |
| Analysis | `scripts/analyze.py` | preset, loudness, low-res flag, background keyability (`flat` digital screens use a tight colour key) |
| Cutting | `scripts/cut.py` | word-gap + silencedetect cuts, filler removal, retake detection; words are protected from being cut as silence |
| Face framing | `scripts/face_frame.py` | BiRefNet-lite ONNX on 3 frames -> face_x / face_y |
| Graphics | `templates/gfx.html` + `scripts/render_gfx.mjs` | every graphic is an HTML page animated frame by frame in headless Chromium (playwright-core); `--batch` renders many in one browser |
| Captions | `scripts/captions.py` | ASS subtitles: bold (karaoke), duo (serif key words), stack, pill, minimal |
| Assembly | `scripts/compose.py` | ffmpeg filter graph per part, 4 parts in parallel, audio once, concat without re-encode |
| Sound | `scripts/sfx_design.py`, `scripts/music.py`, `scripts/make_sfx.py` | sound effects from the plan, synthesised music beds, synthesised SFX pack |
| Edit page | `scripts/live.py`, `scripts/livelog.py`, `templates/live.html` | local server (127.0.0.1) for choosing and watching |
| FilmCraft | `scripts/filmcraft_open.py` | builds the edit on FilmCraft's timeline through its JSON control channel |
| Screen zoom | `scripts/screen_zoom.py` | auto-zoom a screen recording to clicks / typing, vertical output (Screen tutorial style) |
| Gallery | `scripts/make_gallery.py` | style/look preview images (illustrated presenter) |
| Reference study | `scripts/learn_style.py` | downloads/reads a reference reel: contact sheet, cuts per minute, music level, SFX hits |

Key data files (all inside `<video name>_edit/` next to the video):
`words.json`, `words_cut.json`, `segments.json`, `analysis.json`, `intake.json`, `choice.json`, `answers.json`,
`plan.json` (the full edit: inserts, overlays, captions, music, grade...; schema at the top of `compose.py`),
`live.json` (progress), `work_compose/` (renders, args_*.json with the exact ffmpeg commands).

Styles: `styles/edit_styles.json` (Clean cards = `mixed`, Bold B-roll = `studio`, Face and captions = `simple`,
AI News = `news`, Screen tutorial = `tutorial`),
`styles/themes.json` (colour looks), `styles/presets.json` (per content type).

## Run it without Claude

Any agent can drive the same flow with a shell:

```powershell
$PY = ".venv\Scripts\python.exe"                       # made by install.ps1
& $PY scripts\live.py "D:\clips\video.mp4"              # edit page -> open http://127.0.0.1:8765 in any browser
& $PY scripts\autoedit.py "D:\clips\video.mp4" --analyze
# the user presses Start editing -> D:\clips\video_edit\choice.json appears
# map choice.json to answers.json (see SKILL.md section 0, step 3), then:
& $PY scripts\autoedit.py "D:\clips\video.mp4" --answers "D:\clips\video_edit\answers.json" --no-render
# add inserts/overlays to plan.json (the judgement part: cards, stickers, text in the speaker's own words)
& $PY scripts\compose.py "D:\clips\video_edit\plan.json"
& $PY scripts\filmcraft_open.py "D:\clips\video.mp4"   # optional
```

One shot with no questions and no hand-made graphics: `& $PY scripts\autoedit.py video.mp4`.
Render one graphic still: `node scripts/render_gfx.mjs x '{"type":"checklist",...}' --w 1080 --h 1920 --dur 3 --still 2 out.png`.

**What the agent (LLM) is for:** reading `transcript.srt` / `words_cut.json`, catching misheard names (`"fix"` in
plan.json), choosing where cards and stickers go, writing on-screen text in the speaker's own words, and looking
at stills before handing over. Everything else is scripts. A local model can do this part; give it this file,
`SKILL.md`, the transcript and `plan.json`.

Claude-specific tools in `SKILL.md` and their plain equivalents:
- AskUserQuestion / inline widgets -> the edit page (`choice.json`) or a plain numbered question in chat.
- Browser pane -> any browser at `http://127.0.0.1:8765`.
- Background tasks -> run the commands in separate terminals or as background processes.
- `skills/humanizer/SKILL.md` -> read it and apply its rules to every word written on screen.

## Rules (do not break these)

1. **Licences:** only MIT, ISC or OFL code/assets get bundled. Anything else (Apache-only, LGPL, Zlib, no licence)
   is opt-in through an `install.ps1` switch and listed in `LICENSES.md`. Check before adding a dependency.
2. **Never disable or work around Windows security** (Smart App Control, Defender). If a new DLL is blocked on first
   load, wait and retry; tell the user. Never suggest turning protection off.
3. **Never commit or push user media**: videos, audio, renders, `*_edit/` folders, snapshots, FilmCraft projects.
   `.gitignore` blocks them; check `git status` before every commit and ask the user before pushing.
4. **Privacy:** the user's videos stay local. Never put personal details (names, emails) in code, docs, commits or
   requests to outside services. README screenshots must not show the user's face or transcript.
5. **Wording sounds human:** all on-screen text goes through `skills/humanizer/SKILL.md`, using the speaker's own
   transcript as the voice. Sentence case, no em dashes, no arrows or ALL CAPS for emphasis, no phrases the speaker
   never said.
6. **Look:** default is "Clean Paper" (off-white #F4F2EC, black text, blue #2F6FED, yellow highlighter #FFE45C).
   No dark + orange glow, 3D or aurora as defaults: the user said they look AI-generated. No other company's logos
   in graphics (use generic icons and write the name).
7. **Report real wall-clock times**, never estimates as facts. Measure quality changes with SSIM against a
   near-lossless reference before claiming "same quality".
8. **Ask before** slow or heavy steps (AI upscaling ~70 min per minute of video), downloads the user did not ask
   for, and anything that publishes.

## Working conventions

- **Two copies of the skill:** the git repo is this folder (`E:\Reel editing test- real footage\pro-video-editor`);
  Claude Code runs the installed copy at `%USERPROFILE%\.claude\skills\pro-video-editor`. Edit one, copy the changed
  files to the other, and check with `diff -rq` before committing. `install.ps1` copies repo -> installed.
- **Every change:** note it in `CHANGELOG.md` (version + date), update `SKILL.md` if the workflow changes, and
  record measurements in `references/engineering-notes.md`.
- **Test on real footage**, then pull stills (`ffmpeg -ss T -i out.mp4 -frames:v 1 still.png`) and look at them
  before saying it works. The user's test videos live outside the repo (see the workspace `AGENTS.md` one level up).
- **ffmpeg 7+:** pass long filter graphs with `-/filter_complex file.txt`. Phone videos are often stored sideways
  with a rotate flag: use display size (see `probe_wh` in `compose.py`).
- **Graphics templates:** add a new type as another `else if(TYPE==='...')` block in `templates/gfx.html`
  (params via `P('name')`, animate in `render(t)`, end with `outT(t)` fade). Add its sound in `sfx_design.py`.
  Re-run `scripts/make_gallery.py` if the look of a style changes.
- **Windows shell quirks:** writing Python with backslash escapes through a shell heredoc corrupts `\b`, `\f`,
  `\t`; write scripts to a file with an editor instead.
- **Commits:** clear message of what and why; never `--no-verify`.

## Status (keep this section current)

Version: see `CHANGELOG.md` (1.9.2 at the time of writing).

Done: five styles (Clean cards, Bold B-roll, Face and captions, AI News, Screen tutorial) + describe-your-own, edit page with live progress and FilmCraft panel, retake and filler
cutting, clean voice, five caption styles, graphics library (title, chapter, lower, counter, prompt, diagram,
checklist, sticker, band, bignum, device, ctaword, endcard, comment, step header), music + SFX, green-screen
swap with fringe fix, FilmCraft hand-off, render 44% faster than v1.8, README with screenshots.

Next:
- Replace the illustrated gallery with the user's AI-generated storyboard images (one per style, in
  `E:\Reel editing test- real footage\template_images\`; Clean cards is there, Bold B-roll and Face and captions
  to come). Rebuild the edit page tiles and README from them.
- Background-swap renders do not yet use the fast source-resolution path in `compose.py`.
- Despill for green-screen also cools green clothes; option to limit it to the edge band.
- Long-form (30 min) workflow end-to-end test with chapters, B-roll and the bubble layout.
- macOS / Linux installer (scripts are cross-platform; `install.ps1` is Windows-only).

## Glossary

- **Insert:** something that replaces or splits the picture for a time range (`mode`: `top` = top panel, `card` =
  full-screen card on the page canvas, `full` = full frame, `bubble` = screen recording with face bubble).
- **Overlay:** a transparent graphic on top (stickers, big numbers, CTA, wipes).
- **Punch / zoom-in:** short punch-ins on the face (`punch` in plan.json).
- **Keyable:** background that can be swapped cleanly (green/blue screen or plain wall far from skin colours).
