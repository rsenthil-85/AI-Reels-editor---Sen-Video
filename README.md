# pro-video-editor

One Claude Code skill for professional video editing. Give it a video, and either describe the edit you
want or just say "edit this". It picks a style, cuts the dead air, cleans the voice, adds captions, graphics,
music and colour, and exports a ready-to-post file.

## Install (Windows)

Needs: Python 3.10-3.12 from python.org, Node.js LTS, ffmpeg (`winget install Gyan.FFmpeg`).

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -WithRNNoise
```

Takes 5-10 minutes the first time (downloads the Whisper speech model, ~480 MB). If Windows Smart App
Control briefly blocks a new library, the installer waits and retries; it never turns protection off.

## Use

In Claude Code, from any folder:

- "Edit `D:\clips\my-reel.mp4`" - automatic style
- "Edit `talk.mp4` into a 60 s reel with bold yellow captions and upbeat music"
- "Clean the audio on `podcast.mp4` and remove the background voices"
- "Make a montage of the clips in `D:\trip` to cinematic music"

Command line (no Claude): `.venv\Scripts\python.exe scripts\autoedit.py <video> [--preset NAME]`

How a video goes: you upload it, the editor shows the three editing styles as pictures straight away
(`assets/gallery/styles.jpg`) while it analyses the video in the background, asks length and extras, then edits,
checks stills and hands back the file.

Editing styles (`styles/edit_styles.json`):
- **Bold B-roll** - hook title band, warm cinematic face, full-screen phone/laptop shots with big numbers per point,
  stacked-word captions, glowing "Comment" CTA, end card.
- **Clean cards** - cards above your face in a rounded window, full-screen cards, serif key-word captions.
- **Face and captions** - your face all the way, zoom-ins, word-highlight captions, title, stickers, recap checklist.

Not in this repo (too big for GitHub, downloaded on install or on first use): the Whisper speech model, the
BiRefNet person model (`install.ps1`), and the narrator voice for vendor/lemo-opuscar (`kokoro-v1.0.onnx` and
`voices-v1.0.bin`, ~340 MB, from the kokoro-onnx project releases, into `vendor/lemo-opuscar/core/tts/`).

Presets: ai-explainer-reel, talking-head-reel, tutorial-long, talking-head-long, podcast-clip,
cinematic-montage, product-launch (see `styles/presets.json`).

Speed on a 4-core laptop CPU (no NVIDIA GPU): a 1-minute reel goes from upload to finished file in about
5-7 minutes; a fix to one graphic re-renders in about 2.5 minutes. Details: references/engineering-notes.md.
Recording advice (incl. green screen for background swap): references/recording-guide.md.

Licences: see `LICENSES.md`. Everything bundled is MIT, ISC or OFL; non-MIT extras are opt-in.
