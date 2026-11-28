# Licences

**This skill's own code** (scripts/, templates/, styles/, SKILL.md, install.ps1, music.py's synthesised music,
make_sfx.py's sound effects): MIT.

## Bundled third-party code (vendor/)
| Component | Licence |
|---|---|
| lemo-opuscar (LemoLab) | MIT | (its midcentury-toon engine is bundled in templates/toon/, licence: templates/toon/LICENSE-lemo-opuscar.txt) |
| pixelfx (patch-gg) - minus `gallery/fonts` (Patch's own font, not MIT, removed) | MIT (see its NOTICE.md) |
| mcp-for-blender (Siddharth Ahuja) | MIT (+ its TERMS_AND_CONDITIONS.md on telemetry) |
| ClaudeAnimationBase (John Heibel) | MIT |
| react-three-rapier (pmndrs) | MIT |
| react-postprocessing (pmndrs) | MIT |
| awesome-opus5-5-videos (yihui-dev) | MIT |
| humanizer (Siqi Chen / blader) - also in skills/humanizer | MIT |

## Bundled assets
| Asset | Licence |
|---|---|
| Poppins, Instrument Serif, Archivo Black, DM Serif Display fonts | SIL Open Font License 1.1 (OFL files in assets/fonts) |
| Lucide icons (subset) | ISC (assets/icons/LICENSE-lucide.txt) |
| Sound effects (assets/sfx) | MIT - synthesised by make_sfx.py |
| skills/yt-* | copied from the user's YouTube channel folder - confirm their origin and licence before sharing this skill |

## Installed at setup (not bundled)
| Package | Licence | Required |
|---|---|---|
| three | MIT | yes |
| faster-whisper, CTranslate2, Whisper "small" weights | MIT | yes |
| Whisper large-v3-turbo weights (mobiuslabsgmbh/faster-whisper-large-v3-turbo) - Tamil, Hindi and other languages; bundled in assets/models/whisper-large-v3-turbo by install.ps1 (skip with -NoBigSpeech), kept out of git (1.6 GB) | MIT | default |
| librosa | ISC | yes (beat sync) |
| fonttools | MIT | yes |
| numpy, soundfile | BSD-3 | yes |
| Pillow | MIT-CMU | yes |
| playwright-core + Chromium headless shell | Apache-2.0 / BSD-3 | yes (graphics renderer; also required by lemo-opuscar) |
| ffmpeg | LGPL/GPL (user-installed tool, not redistributed) | yes |
| BiRefNet-lite ONNX model (ZhengPeng7, onnx-community) + onnxruntime - auto face framing and background matte (skip with -NoModels) | MIT / MIT | default |
| RNNoise models (GregorR/rnnoise-models) | no licence file - opt-in `-WithRNNoise` | no |
| postprocessing (Zlib), @dimforge/rapier3d-compat (Apache-2.0), p5 (LGPL-2.1) | not MIT/ISC - opt-in `-AllowNonMIT` | no |

Excluded: Vincentwei1021/video-shotcraft (Apache-2.0), joeseesun/opus-video-prompts (no licence),
Real-ESRGAN model weights (BSD-3; `upscale.py` works only if the user supplies them).
