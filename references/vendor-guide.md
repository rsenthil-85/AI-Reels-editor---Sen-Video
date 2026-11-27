# Vendored repos - what each is for and how to use it here

All copied in `vendor/` with their LICENSE files. Git history removed. Licence check done 2026-11-27.

| Repo | Licence | Runtime deps (licence) | Use it for | How |
|---|---|---|---|---|
| lemomo-ai/lemo-opuscar | MIT | playwright-core (Apache-2.0), three (MIT) | Whole films / explainers made in code, 99 styles (oil paint, watercolour, ukiyo-e, satellite briefing, exploded teardown...) | Read `vendor/lemo-opuscar/README.md` + `DIRECTOR.md`; build a demo page, render with its `core/render/video.mjs`, then use the mp4 as an insert (`mode: full`) in plan.json |
| patch-gg/pixelfx | MIT (Patch font removed: not MIT) | none | 244 pixel-art VFX: fire, sparkles, coin drop, lightning, "pow" impacts | `node vendor/pixelfx/tools/render.mjs` / `sheets.mjs` to export an effect as frames, `ffmpeg` them to an alpha .mov, add as an overlay |
| mrdoob/three.js | MIT | - | 3D titles and scenes | Installed from npm (`node_modules/three`); `templates/title3d.html` shows the pattern (page with `window.render(t)`, rendered by `render_gfx.mjs --template`) |
| ahujasid/mcp-for-blender | MIT | Blender; sends anonymous usage telemetry by default (`DISABLE_TELEMETRY=1` turns it off) | 3D product shots / scenes in Blender driven by Claude | Only if the user has Blender. Follow its README to add the MCP server; render shots out of Blender and insert them |
| JohnHeibel/ClaudeAnimationBase | MIT | p5 (LGPL-2.1), p5.brush (MIT), puppeteer-core (Apache-2.0) | Hand-painted 2D character animation | Opt-in (`install.ps1 -AllowNonMIT` for p5). The "Clawd" character is Anthropic's mascot: fine for personal videos, never as a product's branding |
| pmndrs/react-three-rapier | MIT | @dimforge/rapier3d-compat (Apache-2.0), React | Physics in 3D scenes (falling letters, collisions) | Reference only unless -AllowNonMIT; without it, fake simple physics in three.js |
| pmndrs/react-postprocessing | MIT | postprocessing (Zlib), React | Glow, film grain, chromatic aberration, DOF | Reference only unless -AllowNonMIT; three's own `UnrealBloomPass` (MIT) is used by title3d |
| yihui-dev/awesome-opus5-5-videos | MIT | - | 703 prompts for code-made motion graphics | Browse `prompts/` and `data/videos.json` for ideas; write original code, don't copy creators' videos |
| blader/humanizer | MIT | - | Makes every piece of wording read like a person wrote or said it (26 AI-writing patterns) | Default: `skills/humanizer/SKILL.md`, embedded mode, transcript as the voice sample |
| librosa (PyPI) | ISC | numpy, scipy, soundfile, numba (BSD) | Beat/bar detection for cutting on the beat | `scripts/beats.py` |

Excluded on licence grounds: Vincentwei1021/video-shotcraft (Apache-2.0) and joeseesun/opus-video-prompts (no licence).
