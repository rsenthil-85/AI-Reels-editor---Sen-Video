// Mid-century cartoon cut-aways (Lemo-Opuscar's midcentury-toon engine, MIT - see LICENSE-lemo-opuscar.txt).
// Our own creator and robot, five reusable scenes. Every video gets its own cast (p.cast, made by scripts/toon_cast.py):
// the creator's skin, shirt, hair, beard and glasses, the robot's colours and shape, the room palette and wall decor. Drawn in a 1080x1920 design space, scaled to the canvas.
//   scene: struggle | relief | machine | beforeafter | checklist      labels: l1, l2 / items "a|b|c"
import { PAL, setClock, shape, ink, plane, text, star, sparkle, rays, ellipse, rrect, rect, spline, xform,
         seg, eo, back, ss, lerp, TAU, twos, paperFinish, fit, measure } from './engine/toon.js';
import { drawHand } from './engine/chars.js';

const DW = 1080, DH = 1920;
const C = { olive: PAL.avocado, oliveD: PAL.avocadoD, jumper: PAL.coral, jumperD: PAL.coralD };
const DEF = { skin: PAL.skin, skinD: PAL.skinD, hair: PAL.hair, hairStyle: 'side', beard: 'none', glasses: false,
  shirt: PAL.coral, shirtD: PAL.coralD, prop: PAL.avocado, pal: 0, decor: [], seed: 7,
  bot: { body: PAL.blueL, head: PAL.white, face: PAL.tealDD, eye: PAL.tealL, acc: PAL.coral, shape: 'round', antenna: 'ball' } };
let K = DEF;
// room colours per role: problem (struggle, before), fix (relief, after), how (machine), list (checklist)
const PALS = [
  { problem: [PAL.mustardL, PAL.mustardD], fix: [PAL.tealL, PAL.tealD], how: [PAL.blueL, PAL.blueD], list: [PAL.pink, PAL.pinkD] },
  { problem: [PAL.coralL, PAL.coralD], fix: [PAL.avocadoL, PAL.avocadoD], how: [PAL.mustardL, PAL.kraftD], list: [PAL.blueL, PAL.blueD] },
  { problem: [PAL.pink, PAL.pinkD], fix: [PAL.blueL, PAL.blueD], how: [PAL.avocadoL, PAL.avocadoD], list: [PAL.mustardL, PAL.mustardD] },
  { problem: [PAL.kraftL, PAL.kraftD], fix: [PAL.tealL, PAL.tealDD], how: [PAL.pink, PAL.pinkD], list: [PAL.avocadoL, PAL.avocadoD] },
  { problem: [PAL.paperD, PAL.brownL], fix: [PAL.mustardL, PAL.mustardD], how: [PAL.tealL, PAL.tealD], list: [PAL.coralL, PAL.coralD] },
];
const pal = role => (PALS[K.pal] || PALS[0])[role];
export function setCast(p) {
  let c = {}; try { c = p.cast ? JSON.parse(p.cast) : {}; } catch (e) { c = {}; }
  K = Object.assign({}, DEF, c, { bot: Object.assign({}, DEF.bot, c.bot || {}) });
  C.olive = K.prop; C.jumper = K.shirt; C.jumperD = K.shirtD;
}

// ---------------------------------------------------------------- shared pieces
function room(ctx, wall, ground, floorY = 1620) {
  plane(ctx, rect(-1200, -200, DW + 2400, floorY + 200), wall);
  plane(ctx, rect(-1200, floorY, DW + 2400, 600), ground);
  (K.decor || []).forEach((d, i) => decor(ctx, d, i ? 'right' : 'left', floorY));
  ink(ctx, [[-1200, floorY], [420, floorY]], 5, { seed: 2, taper: false }); ink(ctx, [[480, floorY], [DW + 1200, floorY]], 5, { seed: 3, taper: false });
}
function decor(ctx, kind, side, floorY) {   // one piece of wall / floor furniture, the same in every scene of a video
  const L = side === 'left', x = L ? 150 : 930;
  if (kind === 'window') {
    shape(ctx, rrect(x - 105, 150, 210, 250, 14), { fill: PAL.blueL, line: 4.5, seed: 400, grain: 0.15, shade: [{ pts: rect(x - 105, 150, 210, 70), color: PAL.white, alpha: 0.5 }] });
    ink(ctx, [[x, 150], [x, 400]], 5, { seed: 401, taper: false }); ink(ctx, [[x - 105, 275], [x + 105, 275]], 5, { seed: 402, taper: false });
    shape(ctx, rect(x - 125, 396, 250, 22), { fill: PAL.kraft, line: 3.6, seed: 403, grain: 0.2 });
  } else if (kind === 'frame') {
    shape(ctx, rect(x - 95, 170, 190, 240), { fill: PAL.kraftD, line: 4.5, seed: 410, grain: 0.2 });
    shape(ctx, rect(x - 75, 190, 150, 200), { fill: PAL.paper, line: 3, seed: 411, grain: 0.1 });
    shape(ctx, xform(spline([[-1, -0.25], [-0.2, -0.05], [0.15, -0.55], [0.95, -0.2], [0.35, 0.1], [0.1, 0.45], [-0.85, 0.35]], true, 10), x, 290, 0.4, 58), { fill: K.bot.acc, line: 3, seed: 412, grain: 0.2 });
  } else if (kind === 'plant') {
    const px = L ? 70 : 1010, top = floorY - 330;
    for (let i = 0; i < 5; i++) { const a = -1.9 + i * 0.45; shape(ctx, xform(ellipse(0, -70, 30, 82, 20), px, floorY - 150, a * 0.5), { fill: i % 2 ? PAL.avocado : PAL.avocadoD, line: 3.2, seed: 420 + i, grain: 0.2 }); }
    shape(ctx, spline([[px - 60, floorY - 160], [px + 60, floorY - 160], [px + 44, floorY], [px - 44, floorY]], true, 3), { fill: PAL.coral, line: 4, seed: 426, grain: 0.25 });
  } else if (kind === 'lamp') {
    const px = L ? 80 : 1000;
    ink(ctx, [[px, floorY], [px, floorY - 520]], 7, { seed: 430, taper: false });
    shape(ctx, spline([[px - 70, floorY - 520], [px + 70, floorY - 520], [px + 44, floorY - 640], [px - 44, floorY - 640]], true, 3), { fill: PAL.mustardL, line: 4, seed: 431, grain: 0.2 });
    shape(ctx, ellipse(px, floorY - 6, 60, 14, 24), { fill: PAL.ink, line: 0, grain: 0, off: [0, 0] });
  } else if (kind === 'shelf') {
    shape(ctx, rect(x - 120, 380, 240, 20), { fill: PAL.brown, line: 3.6, seed: 440, grain: 0.2 });
    [[PAL.coral, 30, 110], [PAL.teal, 26, 96], [PAL.mustard, 34, 120], [PAL.plum, 24, 90]].forEach(([c, w, h], i) => {
      const bx = x - 100 + [0, 36, 66, 104][i]; shape(ctx, rect(bx, 380 - h, w, h), { fill: c, line: 3, seed: 441 + i, grain: 0.15 }); });
    shape(ctx, ellipse(x + 75, 345, 28, 34, 20), { fill: PAL.avocado, line: 3, seed: 446, grain: 0.2 });
  } else if (kind === 'clockwall') {
    star(ctx, x, 270, 120, { n: 12, inner: 0.55, fill: PAL.mustard, off: [0, 0], rot: 0.1 });
    shape(ctx, ellipse(x, 270, 56, 56, 32), { fill: PAL.white, line: 4, seed: 450, grain: 0.1 });
  }
}
function hairShape(ctx, st) {   // drawn over the head (the 'long' back part is drawn before it)
  const f = { fill: K.hair, line: 3.6, seed: 12, grain: 0.2, breaks: 0.2 };
  if (st === 'bald') { shape(ctx, ellipse(-62, -8, 14, 26, 14), f); return; }
  if (st === 'short') { shape(ctx, spline([[-72, -26], [-68, -82], [-8, -100], [50, -82], [50, -66], [-8, -82], [-48, -62], [-58, -24]], true, 6), f); return; }
  if (st === 'curly') { for (let i = 0; i < 9; i++) { const a = Math.PI * (1.02 + i * 0.105); shape(ctx, ellipse(Math.cos(a) * 74 - 6, Math.sin(a) * 78 - 14, 26, 24, 14), Object.assign({}, f, { seed: 12 + i })); }
    shape(ctx, ellipse(-62, -18, 22, 34, 14), f); return; }
  if (st === 'spiky') { shape(ctx, spline([[-74, -20], [-86, -70], [-52, -78], [-50, -116], [-14, -92], [6, -126], [26, -92], [58, -104], [50, -62], [-6, -72], [-40, -54], [-54, -14]], true, 2), f); return; }
  shape(ctx, spline([[-74, -20], [-70, -78], [-10, -104], [54, -84], [50, -56], [-6, -70], [-40, -52], [-54, -14]], true, 6), f);   // side parting
  if (st === 'bun') shape(ctx, ellipse(-30, -112, 32, 28, 20), Object.assign({}, f, { seed: 19 }));
}
function head(ctx, x, y, mood, t, s = 1) {
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  if (K.hairStyle === 'long') shape(ctx, spline([[-60, -70], [-96, -10], [-96, 96], [-40, 110], [-30, 20]], true, 6), { fill: K.hair, line: 3.6, seed: 10, grain: 0.2 });
  const H_ = spline([[46, -70], [-10, -92], [-70, -60], [-78, 10], [-50, 70], [10, 82], [48, 52], [56, 22], [82, 14], [58, -8], [60, -40]], true, 6);
  shape(ctx, H_, { fill: K.skin, line: 4.2, seed: 11, grain: 0.25, breaks: 0.15, shade: [{ pts: [[-90, -100], [-40, -100], [-52, 90], [-90, 90]], color: K.skinD, alpha: 0.45 }] });
  hairShape(ctx, K.hairStyle);
  if (K.beard === 'full' || K.beard === 'stubble')
    shape(ctx, spline([[-52, 18], [-50, 70], [10, 88], [50, 58], [60, 26], [44, 30], [36, 58], [4, 66], [-26, 40]], true, 6),
      { fill: K.hair, line: K.beard === 'full' ? 3.2 : 0, seed: 14, grain: 0.3, alpha: K.beard === 'full' ? 1 : 0.32, off: [0, 0] });
  const blink = (Math.floor(t * 12) % 30) === 0;
  if (mood === 'worried') {
    ink(ctx, [[-6, -40], [34, -30]], 4, { seed: 13 }); ink(ctx, [[38, -30], [62, -42]], 4, { seed: 14 });
    shape(ctx, ellipse(14, -12, 7, blink ? 1.5 : 9, 14), { fill: PAL.ink, line: 0, off: [0, 0], grain: 0 });
    shape(ctx, ellipse(50, -12, 7, blink ? 1.5 : 9, 14), { fill: PAL.ink, line: 0, off: [0, 0], grain: 0 });
    ink(ctx, spline([[6, 44], [18, 36], [30, 46], [42, 36], [52, 44]], false, 4), 3.6, { seed: 15 });
  } else {
    ink(ctx, spline([[2, -14], [14, -26], [26, -14]], false, 4), 4, { seed: 16 });
    ink(ctx, spline([[38, -14], [50, -26], [62, -14]], false, 4), 4, { seed: 17 });
    shape(ctx, spline([[4, 30], [30, 58], [58, 30]], true, 6), { fill: PAL.coralD, line: 3.6, seed: 18, grain: 0 });
  }
  if (K.beard === 'moustache') shape(ctx, spline([[6, 22], [30, 12], [60, 20], [54, 30], [30, 24], [10, 32]], true, 4), { fill: K.hair, line: 2.6, seed: 19, grain: 0.2 });
  if (K.glasses) {
    const gy = mood === 'worried' ? -12 : -18;
    [14, 50].forEach((gx, i) => shape(ctx, ellipse(gx, gy, 20, 18, 24), { fill: 'rgba(251,246,234,0.22)', line: 4, seed: 26 + i, grain: 0, off: [0, 0] }));
    ink(ctx, [[34, gy - 2], [30, gy - 2]], 4, { seed: 28, taper: false }); ink(ctx, [[-6, gy - 4], [-46, gy - 10]], 4, { seed: 29, taper: false });
  }
  ctx.restore();
}
function creator(ctx, t, pose, x = 540, y = 1010, s = 1) {   // held body; only arms, hands, eyes and mouth move (on twos)
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  const tt = twos(t);
  shape(ctx, spline([[-130, 220], [-120, -40], [-60, -96], [60, -96], [120, -40], [130, 220]], true, 6),
    { fill: C.jumper, line: 4.2, seed: 21, grain: 0.35, breaks: 0.2, shade: [{ pts: [[40, -120], [160, -120], [160, 240], [60, 240]], color: C.jumperD, alpha: 0.5 }] });
  if (pose === 'type') {
    const a = Math.sin(tt * 26) * 12, b = Math.cos(tt * 26) * 12;
    ink(ctx, [[-110, -30], [-150, 70], [-92, 132 + a]], 30, { seed: 22, taper: false, color: C.jumper });
    ink(ctx, [[110, -30], [150, 70], [92, 132 + b]], 30, { seed: 23, taper: false, color: C.jumper });
    drawHand(ctx, -92, 140 + a, 0.2, 'flat', 1, 1.3, K.skin); drawHand(ctx, 92, 140 + b, Math.PI - 0.2, 'flat', -1, 1.3, K.skin);
    head(ctx, 0, -190 + Math.sin(tt * 26) * 2, 'worried', t);
  } else if (pose === 'point') {
    ink(ctx, [[-110, -30], [-150, 70], [-100, 150]], 30, { seed: 22, taper: false, color: C.jumper });
    const up = Math.sin(tt * 4) * 6;
    ink(ctx, [[110, -40], [210, -150], [250, -300 + up]], 30, { seed: 23, taper: false, color: C.jumper });
    drawHand(ctx, 250, -310 + up, -1.3, 'point', 1, 1.3, K.skin);
    head(ctx, -4, -196, 'happy', t);
  } else {
    ink(ctx, [[-110, -40], [-190, -170], [-70, -250]], 30, { seed: 24, taper: false, color: C.jumper });
    ink(ctx, [[110, -40], [190, -170], [70, -250]], 30, { seed: 25, taper: false, color: C.jumper });
    head(ctx, -8, -204, pose === 'sad' ? 'worried' : 'happy', t);
  }
  ctx.restore();
}
function desk(ctx, glow, y = 1040) {
  shape(ctx, rrect(380, y, 320, 200, 18), { fill: PAL.chrome, line: 4.2, seed: 31, grain: 0.2, shade: [{ pts: rect(380, y, 320, 30), color: glow, alpha: 0.9 }] });
  shape(ctx, ellipse(540, y + 100, 22, 22, 24), { fill: PAL.chromeD, line: 3, seed: 32, grain: 0 });
  shape(ctx, rect(130, y + 195, 820, 66), { fill: PAL.mustardD, line: 4.5, seed: 33, grain: 0.3, breaks: 0.15 });
  shape(ctx, rect(180, y + 260, 56, 330), { fill: PAL.mustardD, line: 4, seed: 34, grain: 0.3 });
  shape(ctx, rect(844, y + 260, 56, 330), { fill: PAL.mustardD, line: 4, seed: 35, grain: 0.3 });
}
function clip(ctx, x, y, r, s = 1, seed = 0) {
  shape(ctx, xform(rrect(-70, -42, 140, 84, 10), x, y, r, s), { fill: C.olive, line: 3.8, seed: 40 + seed, grain: 0.25 });
  for (let i = 0; i < 3; i++) shape(ctx, xform(rect(-54 + i * 38, -26, 30, 52), x, y, r, s), { fill: PAL.white, line: 2.6, seed: 50 + seed + i, grain: 0 });
}
function videoCard(ctx, x, y, s = 1) {
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  shape(ctx, rrect(-200, -125, 400, 250, 24), { fill: PAL.white, line: 4.5, seed: 120, grain: 0.15 });
  shape(ctx, spline([[-34, -56], [56, 0], [-34, 56]], true, 3), { fill: PAL.coral, line: 4, seed: 121, grain: 0.2 });
  ctx.restore();
}
function tickStamp(ctx, x, y, k, s = 1) {   // tick in a starburst, pops with a back-ease
  if (k <= 0) return; ctx.save(); ctx.translate(x, y); ctx.scale(k * s, k * s);
  rays(ctx, 0, 0, 24, 140, PAL.mustardL, { alpha: 0.5 }); star(ctx, 0, 0, 92, { n: 14, inner: 0.82, fill: PAL.mustard, off: [0, 0], rot: 0.2 });
  shape(ctx, ellipse(0, 0, 62, 62, 40), { fill: PAL.teal, line: 4.5, seed: 130, grain: 0.2 });
  ink(ctx, [[-26, 2], [-6, 24], [30, -22]], 12, { seed: 131, taper: false, color: PAL.white }); ctx.restore();
}
function clockFace(ctx, cx, cy, R, t, speed) {
  shape(ctx, ellipse(cx, cy, R + 18, R + 18, 72), { fill: PAL.paper, line: 4.5, seed: 100, grain: 0.15 });
  shape(ctx, ellipse(cx, cy, R, R, 64), { fill: PAL.white, line: 5, seed: 60, grain: 0.15 });
  for (let i = 0; i < 12; i++) { const a = i * TAU / 12; ink(ctx, [[cx + Math.cos(a) * R * 0.78, cy + Math.sin(a) * R * 0.78], [cx + Math.cos(a) * R * 0.9, cy + Math.sin(a) * R * 0.9]], 4, { seed: 61 + i, taper: false }); }
  const tt = twos(t), a1 = tt * speed, a2 = tt * speed / 12;
  ink(ctx, [[cx, cy], [cx + Math.sin(a1) * R * 0.72, cy - Math.cos(a1) * R * 0.72]], 6, { seed: 80, taper: false });
  ink(ctx, [[cx, cy], [cx + Math.sin(a2) * R * 0.5, cy - Math.cos(a2) * R * 0.5]], 10, { seed: 81, taper: false });
  shape(ctx, ellipse(cx, cy, 10, 10, 16), { fill: PAL.ink, line: 0, off: [0, 0], grain: 0 });
}
function robot(ctx, t, x = 820, y = 1060, s = 1, typing = true) {
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  const tt = twos(t), yy = Math.sin(tt * 6) * 5, a = Math.sin(tt * 22) * 10;
  const B = K.bot;
  if (B.antenna === 'ears') { [-1, 1].forEach(sx => shape(ctx, rrect(sx * 78 - 14, yy - 60, 28, 52, 10), { fill: B.acc, line: 3, seed: 91 + sx, grain: 0 })); }
  else if (B.antenna === 'bolt') shape(ctx, [[-6, yy - 92], [10, yy - 120], [-2, yy - 120], [12, yy - 150], [-14, yy - 116], [-2, yy - 116], [-14, yy - 92]], { fill: B.acc, line: 3, seed: 91, grain: 0 });
  else { ink(ctx, [[0, yy - 130], [0, yy - 90]], 5, { seed: 90, taper: false }); shape(ctx, ellipse(0, yy - 140, 14, 14, 16), { fill: B.acc, line: 3, seed: 91, grain: 0 }); }
  const hd = B.shape === 'dome' ? spline([[-78, yy + 28], [-78, yy - 40], [-40, yy - 96], [40, yy - 96], [78, yy - 40], [78, yy + 28]], true, 6) : rrect(-78, yy - 92, 156, 120, B.shape === 'square' ? 12 : 40);
  shape(ctx, hd, { fill: B.head, line: 4.2, seed: 92, grain: 0.2 });
  shape(ctx, rrect(-56, yy - 72, 112, 74, B.shape === 'square' ? 8 : 20), { fill: B.face, line: 3, seed: 93, grain: 0 });
  shape(ctx, ellipse(-22, yy - 36, 10, 12, 14), { fill: B.eye, line: 0, off: [0, 0], grain: 0 });
  shape(ctx, ellipse(22, yy - 36, 10, 12, 14), { fill: B.eye, line: 0, off: [0, 0], grain: 0 });
  shape(ctx, rrect(-62, yy + 30, 124, 150, 30), { fill: B.body, line: 4, seed: 94, grain: 0.25 });
  if (typing) { ink(ctx, [[-60, yy + 80], [-150, yy + 110], [-196, yy + 118 + a]], 22, { seed: 95, taper: false, color: B.body });
    drawHand(ctx, -200, yy + 120 + a, Math.PI, 'flat', -1, 1.2, PAL.white); }
  ctx.restore();
}
function tag(ctx, t, t0, str, x, y, plate = PAL.mustardL, px = 44) {   // paper tag with a turning star, pops on its beat
  const k = back(seg(t, t0, t0 + 0.25), 2.2); if (k <= 0 || !str) return;
  const f = fit(ctx, str.toUpperCase(), '{px}px Slab', px, 560, 1, 26), w = measure(ctx, f.lines[0], f.font) + 110;
  ctx.save(); ctx.translate(x, y); ctx.scale(k, k); ctx.rotate(-0.06);
  shape(ctx, rrect(-w / 2, -44, w, 88, 16), { fill: PAL.paper, line: 3.6, seed: 110, grain: 0.15 });
  star(ctx, -w / 2 + 34, 0, 18, { n: 8, inner: 0.42, fill: PAL.coral, off: [0, 0], rot: t * 0.6 });
  text(ctx, f.lines[0], 18, f.px * 0.36, { font: f.font, fill: PAL.ink, plate, align: 'center' });
  ctx.restore();
}
function medallion(ctx, x, y, n, k, fill) {
  if (k <= 0) return; ctx.save(); ctx.translate(x, y); ctx.scale(k, k); ctx.rotate((1 - k) * 0.4);
  star(ctx, 0, 0, 62, { n: 16, inner: 0.84, fill: PAL.white, off: [0, 0], rot: n * 0.2 });
  shape(ctx, ellipse(0, 0, 50, 50, 48), { fill, line: 4.5, seed: 730 + n, grain: 0.3 });
  text(ctx, String(n), 0, 20, { font: '56px Slab', fill: PAL.ink, plate: PAL.white, off: [4, 4], align: 'center' });
  ctx.restore();
}

// ---------------------------------------------------------------- the five scenes (u = local seconds, D = scene length)
const SCENES = {
  struggle(ctx, u, D, p) {       // "I used to spend hours..." - worried creator, clips piling up, clock spinning
    room(ctx, ...pal('problem'));
    const n = Math.min(10, 1 + Math.floor(twos(u) / Math.max(0.25, (D - 0.6) / 10)));
    for (let i = 0; i < n; i++) clip(ctx, 860 + ((i * 41) % 70) - 35, 1196 - i * 58, (i % 2 ? -0.12 : 0.14), 1, i);
    creator(ctx, u, 'type');
    for (let i = 0; i < 2; i++) { const ph = (twos(u) * 1.4 + i / 2) % 1; shape(ctx, spline([[650, 730 + ph * 150], [640, 760 + ph * 150], [650, 772 + ph * 150], [660, 760 + ph * 150]], true, 4), { fill: PAL.blueL, line: 3, seed: 70 + i, grain: 0 }); }
    desk(ctx, PAL.blueL);
    const k = back(seg(u, 0.1, 0.42), 1.5); if (k > 0) clockFace(ctx, 540, 420, 170 * k, u, 14);
    tag(ctx, u, Math.min(1.6, D * 0.35), p.l1 || '2 hours', 690, 570);
  },
  relief(ctx, u, D, p) {         // "...so I built an AI that does it" - creator relaxes, robot works, clips fly into a finished video
    room(ctx, ...pal('fix'));
    creator(ctx, u, u < 0.2 ? 'type' : 'relax');
    robot(ctx, u); desk(ctx, PAL.tealL);
    videoCard(ctx, 540, 470);
    const step = Math.max(0.18, (D * 0.55) / 5);
    for (let i = 0; i < 5; i++) { const q = eo(seg(u, 0.5 + i * step, 1.0 + i * step)); if (q <= 0 || q >= 1) continue;
      clip(ctx, lerp(860, 540, q), lerp(1150, 470, q) - Math.sin(q * Math.PI) * 260, q * 4, 1 - q * 0.6, i); }
    tickStamp(ctx, 740, 345, back(seg(u, D * 0.68, D * 0.68 + 0.3), 2.2));
    for (let i = 0; i < 4; i++) { const ph = (u * 0.8 + i / 4) % 1; sparkle(ctx, 540 + Math.cos(i * 1.7) * (260 + ph * 40), 470 + Math.sin(i * 1.7) * (170 + ph * 30), 26 * (1 - ph), { fill: PAL.white }); }
    tag(ctx, u, D * 0.75, p.l1 || '', 540, 700, PAL.tealL);
  },
  machine(ctx, u, D, p) {        // "how it works": raw clips fall into the robot machine, a finished video comes out
    room(ctx, ...pal('how'), 1720);
    // funnel + machine body
    shape(ctx, spline([[300, 560], [780, 560], [620, 780], [460, 780]], true, 3), { fill: PAL.mustard, line: 4.5, seed: 200, grain: 0.3 });
    shape(ctx, rrect(330, 780, 420, 420, 40), { fill: PAL.white, line: 5, seed: 201, grain: 0.2, shade: [{ pts: rect(600, 780, 160, 420), color: PAL.paperD, alpha: 0.6 }] });
    const tt = twos(u);
    for (let g = 0; g < 2; g++) { const cx = 450 + g * 180, cy = 900, rot = tt * (g ? -3 : 3);
      shape(ctx, xform(spline(Array.from({ length: 16 }, (_, i) => { const a = i * TAU / 16, r = i % 2 ? 46 : 60; return [Math.cos(a) * r, Math.sin(a) * r]; }), true, 2), cx, cy, rot), { fill: PAL.mustardL, line: 3.6, seed: 202 + g, grain: 0.2 });
      shape(ctx, ellipse(cx, cy, 16, 16, 16), { fill: PAL.ink, line: 0, off: [0, 0], grain: 0 }); }
    shape(ctx, rrect(380, 1010, 320, 130, 20), { fill: PAL.tealDD, line: 3.6, seed: 204, grain: 0 });
    shape(ctx, ellipse(480, 1075, 16, 20, 14), { fill: PAL.tealL, line: 0, off: [0, 0], grain: 0 }); shape(ctx, ellipse(600, 1075, 16, 20, 14), { fill: PAL.tealL, line: 0, off: [0, 0], grain: 0 });
    // clips drop in from the top, one per beat
    const step = Math.max(0.2, (D * 0.5) / 5);
    for (let i = 0; i < 5; i++) { const q = seg(u, 0.2 + i * step, 0.75 + i * step); if (q <= 0 || q >= 1) continue;
      clip(ctx, 540 + Math.sin(i * 2.1) * 120 * (1 - q), lerp(260, 700, q * q), i * 0.7 + q, 1 - q * 0.4, i); }
    // finished video slides out at the bottom onto the floor
    const out = eo(seg(u, D * 0.6, D * 0.6 + 0.5));
    if (out > 0) { videoCard(ctx, lerp(540, 540, out), lerp(1180, 1440, out), 0.8); tickStamp(ctx, 720, 1340, back(seg(u, D * 0.75, D * 0.75 + 0.3), 2.2), 0.8); }
    tag(ctx, u, 0.4, p.l1 || 'Your video', 540, 470, PAL.mustardL, 40);
    tag(ctx, u, D * 0.7, p.l2 || 'Ready to post', 540, 1640, PAL.tealL, 40);
  },
  beforeafter(ctx, u, D, p) {    // split frame: before (top, mustard) vs after (bottom, teal)
    ctx.save(); ctx.beginPath(); ctx.rect(-1200, -200, DW + 2400, 960 + 200); ctx.clip();
    plane(ctx, rect(-1200, -200, DW + 2400, 1160), pal('problem')[0]);
    ctx.translate(0, -470); ctx.translate(540, 1010); ctx.scale(0.62, 0.62); ctx.translate(-540, -1010);
    for (let i = 0; i < 8; i++) clip(ctx, 860 + ((i * 41) % 70) - 35, 1196 - i * 58, (i % 2 ? -0.12 : 0.14), 1, i);
    creator(ctx, u, 'type'); desk(ctx, PAL.blueL); ctx.restore();
    const k = eo(seg(u, D * 0.3, D * 0.3 + 0.35));              // colour-block wipe, bottom-up
    ctx.save(); ctx.beginPath(); ctx.rect(-1200, 960 + (1 - k) * 960, DW + 2400, 1200); ctx.clip();
    plane(ctx, rect(-1200, 960, DW + 2400, 1200), pal('fix')[0]);
    ctx.translate(0, 480); ctx.translate(540, 1010); ctx.scale(0.62, 0.62); ctx.translate(-540, -1010);
    creator(ctx, u, 'relax'); robot(ctx, u); desk(ctx, PAL.tealL); ctx.restore();
    ink(ctx, [[-1200, 960], [DW + 1200, 960]], 6, { seed: 210, taper: false });
    tag(ctx, u, 0.2, p.l1 || 'Before', 220, 120, pal('problem')[0], 40);
    tag(ctx, u, D * 0.3 + 0.3, p.l2 || 'After', 220, 1060, pal('fix')[0], 40);
    tickStamp(ctx, 880, 1180, back(seg(u, D * 0.7, D * 0.7 + 0.3), 2.2), 0.75);
  },
  checklist(ctx, u, D, p) {      // a paper card of steps ticking one by one; the creator points at it
    room(ctx, ...pal('list'));
    const items = (p.items || 'Cut the pauses|Clean the voice|Add captions').split('|').filter(Boolean).slice(0, 5);
    const cardH = 140 + items.length * 150;
    shape(ctx, rrect(150, 220, 780, cardH, 30), { fill: PAL.paper, line: 5, seed: 300, grain: 0.15 });
    if (p.l1) tag(ctx, u, 0.1, p.l1, 540, 220, PAL.mustardL, 40);
    const step = Math.max(0.3, (D - 1.0) / items.length);
    items.forEach((it, i) => {
      const y = 360 + i * 150, k = back(seg(u, 0.3 + i * step, 0.55 + i * step), 2);
      medallion(ctx, 250, y, i + 1, k, [PAL.coral, PAL.mustard, PAL.teal, PAL.avocado, PAL.blue][i % 5]);
      if (k > 0) { const f = fit(ctx, it, '500 {px}px Jost', 44, 540, 1, 28); text(ctx, f.lines[0], 330, y + f.px * 0.36, { font: f.font, fill: PAL.ink }); }
      const kt = back(seg(u, 0.55 + i * step, 0.8 + i * step), 2.4);
      if (kt > 0) { ctx.save(); ctx.translate(860, y); ctx.scale(kt, kt); ink(ctx, [[-26, 2], [-6, 24], [30, -22]], 12, { seed: 320 + i, taper: false, color: PAL.tealD }); ctx.restore(); }
    });
    creator(ctx, u, 'point', 300, 1500, 0.85);
  },
};

export function renderScene(ctx, W, H, t, p) {
  setClock(t); if (renderScene.castOf !== p.cast) { setCast(p); renderScene.castOf = p.cast; }
  const D = +p.dur || 4, scene = SCENES[p.scene] || SCENES.struggle;
  ctx.save(); ctx.fillStyle = PAL.paper; ctx.fillRect(0, 0, W, H);
  const s = Math.min(W / DW, H / DH) * (H / DH > W / DW ? 1 : 1); const sc = H / DH;   // fit the 9:16 design by height
  ctx.translate((W - DW * sc) / 2, 0); ctx.scale(sc, sc);
  const z = lerp(1, 1.04, ss(t / D));                                    // the stand: a slow push
  ctx.translate(DW / 2, DH / 2); ctx.scale(z, z); ctx.translate(-DW / 2, -DH / 2);
  scene(ctx, t, D, p);
  ctx.restore();
  const k = seg(t, 0, 0.3);                                              // iris in from black at the start
  if (k < 1) { ctx.save(); ctx.fillStyle = PAL.ink; ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.arc(W / 2, H * 0.42, Math.max(W, H) * 1.2 * eo(k), 0, TAU, true); ctx.fill(); ctx.restore(); }
  paperFinish(ctx, W, H, 1);
}
