# Learned styles from reference videos

Each entry: the link the user gave, what was measured, and the rules the skill applies. Add new references
here (download with yt-dlp, `fps=1` contact sheet, scene-cut times, captions) before changing templates.

## "Mixed cards" (default for explainers and how-tos) - from 2 references, 2026-11-27

Refs:
- https://www.youtube.com/shorts/lDJggK3EEug - Error Makes Clever, "Generative AI vs Agentic AI", 69 s, 169k views
- https://youtube.com/shorts/bUr6r1jrlNg - "How to edit (with Claude)", 33 s, step-by-step tutorial

Layout mix (the core idea): the video moves between THREE layouts, not one.
1. **Face only** (full frame) - intro hook, opinions, the ending. Ref 1: 0-7 s and 50-69 s.
2. **Full-screen card** (no face) - when the speaker explains something that is better shown: a step, a
   screenshot, a number, a comparison. Ref 1 holds one for ~20 s (app screenshots floating on a white canvas
   with yellow shapes). Ref 2 opens with one ("How to edit / It's stupidly easy").
3. **Card + face window** - the card on top, the face in a ROUNDED window at the bottom with a margin on the
   same canvas (ref 2), so it reads as one designed page, not two stacked videos.
Rule of thumb for a 30-70 s reel: ~30-40% face only, ~30-40% card + face, ~20-30% full-screen cards.
Start on a full card or the face with a bold title; end on the face with the CTA.

Captions ("duo"): small plain sans words for the run of speech, and the KEY word or phrase on its own line in a
larger italic serif in the accent colour (ref 1: yellow "called Agentic AI"; ref 2: orange "video", "prompt").
On full cards the captions sit under the card content in dark text; on the face they sit low, white.

Cards:
- Step header: small "STEP 03 / 07" label top-left, progress dots top-right, bold heading under it,
  a huge faded step number in the background (ref 2).
- App/UI mock-ups: app window with three dots, prompt typing with key words highlighted, upload 0 -> 100 %,
  progress ring counting up (ref 2); real screenshots floating with a soft shadow (ref 1).
- Keyword badge card: brand names in bold diamond/pill badges (ref 1 "AutoGPT / OpenClaw").
- Strikethrough reveal: "Hours of editing" struck out, then "Not" (ref 2).
- Icon stickers popping in next to the face for tools mentioned (ref 1: ChatGPT logo).
Ending: face full screen + "Comment KEYWORD" pill + a mock comment bubble (ref 2).

Pace: a new card or layout every 2-4 s; short B-roll flashes (0.4-0.6 s) are fine in a hook (ref 1).

In the skill: plan `"layout": "mixed"`; inserts with `"mode": "card"` (full-screen card on the theme canvas),
`"mode": "top"` with `"split_style": "inset"` (rounded face window), captions `"caption_style": "duo"`,
graphics accept `"step": "3/7"`, and type `"comment"` for the CTA.

## Ref 3 - https://youtube.com/shorts/ESMRMpErs-M - Richard Eve, "Everybody's telling you to install Claude skills", 57 s, 40k views

Layout: almost the whole video is **card on top + face in a rounded window below** on a light grey canvas
(same as ref 2's inset), with 2 short full-face beats (a reaction at 10 s, "number three" at 25-28 s).
Accent: one bright blue on white cards. Cuts every ~2-6 s, but the CARD changes every 1-2 s (count-ups, ticks).

New elements seen:
- **Boxed word captions**: words in white, the word being said shown in a dark rounded box (inverted).
- **Count-up stat cards**: "298K -> 510K GitHub stars" with a small bar chart; "#1 Matt Pocock 127K -> 317K".
- **Ranking card**: "#1 / #2 / #3" header strip in the accent colour, avatar + name + stat + "Free" chip.
- **Checklist card**: 4 tiles (icon + title + small code-ish label) ticked one by one with blue checks,
  then a "Proper process" pill.
- **Before / After text card**: a draft with AI phrases struck red ("Before"), then the clean version ("After").
- **Gauge card**: "Sounds like ChatGPT" meter, needle swinging from Human to ChatGPT and back.
- **Numbered chip lower-third** on the face: "3  Every piece of work".
- **Percent ring**: "60% -> 80% of what you need" with avatars.
- End: "Comment FIVE" post-input mock with a cursor, then an install-guide checklist filling in.

Takeaway for the skill: the inset layout is the main layout for tool/tips content; full face only for
reactions and the number beats; every card animates something (count, tick, swing, strike) while on screen.

## Ref 4 - https://youtube.com/shorts/-Lo1X4t1PiI - Error Makes Clever, "Build Project with AI in 30 Seconds", 81 s, 225k views

Tamil + English speech. Mostly FACE full frame (cuts only 4.4/min) kept alive by things popping in:
- Big opening title over the face: "Build this project / **with AI** (huge bold blue) / in 30 mins" + a yellow sparkle star.
- **Icon stickers** popping in at the bottom centre, one per noun (document, ID card, tick, Google Sheet,
  Apps Script logo, red X), each with a pop sound (~7 SFX hits/min).
- Captions "duo" again: small white words + key word in italic serif yellow ("problem", "attendance", "Google Sheet").
- One full-screen white explainer card (~15 s): icons appear and connect step by step
  (School wifi -> IP -> Code -> students -> Attendance) over a hand-drawn green squiggle and a yellow sparkle.
- Short real B-roll (event photos) when telling a story. Channel logo top-right throughout.
Audio: music bed all the way under the voice, ~108 bpm.

## Ref 5 - https://youtube.com/shorts/kWxGJdiCIOM - Ben Kimball AI, "7 FREE Claude Code Skills You NEED", 71 s, 32k views

Black canvas, neon green accent. Card on top, face as a small window below; punch-in to a big full face
on reveals ("freaking", "build"). Countdown list format: "#1 . . . . . . " progress header per item,
GitHub screenshot cards with green highlight boxes, red stamp "AI SLOP", green stamp "NOT HACKED",
stat counters (257 -> 261 skills, 64 agents, 84 commands). Captions: ONE lowercase word at a time,
small, white, centred between card and face. White flash transition before the CTA; "FREE" in quotes over the face.
Audio: very dense sound design - **76 SFX hits/min** (a click/whoosh on almost every change), music ~108 bpm.

## Ref 6 - https://youtube.com/shorts/bBdY_uUbpzk - Levine Tech Talks, "5 Claude Code Skills With 800K+ GitHub Stars", 76 s, 46k views

Purple gradient canvas with soft glow blobs; glassy purple card on top ("Find Skills  * 39.4K"),
face edge-to-edge in the bottom panel with a purple glow line on the seam. Countdown "#5 -> #1" section cards
(full-width title in the top panel: "#4 CLAUDE-MEM", "#3 FAN FAVORITE"), opening "TOP 5 skills you need"
+ "596K+ -> 819K+ GitHub stars combined" counter, highlight boxes on screenshots, step checklist ticking
("Brainstorm first / Write a plan / Small tested steps / Review its own work" + checks), before/after
illustration. Captions: words joined with underscores ("Here_are_five"), the spoken word in a purple box.
End card: "Found this useful?" + Like / Save / Subscribe buttons.
Audio: music ~129 bpm all the way, **55 SFX hits/min**.

## Ref 7 - the user's own reference edit (Senthil Sir Output.mp4, "Make money by creating just one digital product"), 43 s

Studied from the file (learn_style.py now takes a local file). 16.7 cuts/min, music bed 7.5 dB under the voice
(~150 bpm, upbeat), ~57 SFX hits/min (a whoosh on every cut, hits on the numbers).
- **Hook 0-4.5 s**: top = cinematic B-roll (person at a laptop, then the product dashboard), a black band across the
  seam with a bright green heavy headline and a thin italic white second line, the speaker's face below.
- **Face** full frame, warm cinematic grade (brick wall, lamp, amber mids, vignette).
- **Captions "stack"**: lower-case words pile up one per line, left-aligned near the centre, white with a soft
  shadow; the key word of the group bigger in heavy type ("one", "looking", "personal").
- **List points** ("first / second / third / fourth"): full-screen B-roll of the product on a tablet, phone, laptop
  (slow push-in, hands, a cursor tapping, a paper-plane send animation) with a giant slanted lime number on the left.
- **CTA**: small "Comment" + a huge quoted serif word with a blue glow, zooming in from a blur.
- **End card**: black, centred serif lines, one line in yellow ("Community link in bio"), a big round chat-app icon.
In the skill: style **Bold B-roll** (`styles/edit_styles.json` "studio"); graphics band, bignum, device, ctaword,
endcard; captions `stack`; grade `warm`. B-roll: the user's clips/screenshots first; the device mock-up stands in
when there are none. Brand logos are not copied (plain icons instead).

## What all 6 references agree on (apply by default to "mixed cards")

1. Three layouts mixed: face only / card + face (window or panel) / full-screen card.
2. Something moves on the card at least every 1-2 s (count-up, tick, highlight box, icon pop, typing).
3. Captions short and centred; the key word is visually different (serif italic colour, box, or highlight).
4. **Music bed under the whole video, upbeat 105-135 bpm, clearly audible** (gaps only ~4-6 dB under the
   voice by the rough meter) - ours (-23 dB, lofi) is much quieter and slower than all six.
5. **Sound effects on almost every visual change**: from ~7/min (icon pops) to 55-76/min (click per card
   change, tick per checklist item, whoosh per transition). Ours: ~1 whoosh per graphic (~10/min).
6. Countdown/list structure for "N tools / N steps" videos: section cards "#3 NAME" + a progress header.

Built since: SFX on every beat, louder upbeat music, checklist card, icon stickers, Bold B-roll pieces (ref 7).
Not built yet (candidates, most common first): highlight-box on screenshots, stamp ("AI SLOP"),
countdown section card, boxed/underscore word captions, white-flash transition, Like/Save/Subscribe end card,
black-neon and purple-glow themes, before/after card, gauge card.
