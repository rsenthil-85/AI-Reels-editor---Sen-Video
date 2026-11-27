#!/usr/bin/env node
// render_gfx.mjs - render animated graphics from templates/*.html to transparent .mov (qtrle, alpha)
//   node render_gfx.mjs out.mov '{"type":"title","l1":"How to make a","money":"website"}' --w 1080 --h 864 --dur 2.5 [--fps 30] [--still 1.2 out.png]
//   node render_gfx.mjs --batch jobs.json [--workers 3]     jobs = [{"out","params","w","h","dur","template"}]
// Speed (lossless): one browser for every job; a frame whose DOM state equals the previous frame's is not
// screenshotted again - its PNG is reused (DOM templates: the still middle of a card costs nothing).
// Canvas/WebGL templates (motionbg, title3d) have no DOM signature and are captured every frame.
import { chromium } from 'playwright-core';
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path'; import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const a = process.argv.slice(2);
const opt = (k, d) => { const i = a.indexOf('--' + k); return i >= 0 ? a[i + 1] : d; };
const FPS = +opt('fps', 30);

const types = { '.js': 'text/javascript', '.mjs': 'text/javascript', '.html': 'text/html', '.ttf': 'font/ttf', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp' };
const srv = http.createServer((req, res) => {
  const p = decodeURIComponent(req.url.split('?')[0]);
  const f = p.startsWith('/abs/') ? p.slice(5) : path.join(ROOT, p);
  fs.readFile(f, (e, b) => { if (e) { res.writeHead(404); return res.end(); } res.writeHead(200, { 'content-type': types[path.extname(f).toLowerCase()] || 'application/octet-stream' }); res.end(b); });
}).listen(0);
const port = srv.address().port;
const browser = await chromium.launch({ args: ['--font-render-hinting=none', '--force-color-profile=srgb'] });

async function job({ out, params, w = 1080, h = 864, dur = 2.5, template = 'gfx.html', still = null, stillOut = null, opaque = false, fps = FPS }) {
  const q = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])); q.set('w', w); q.set('h', h); q.set('dur', dur);
  for (const k of ['photo', 'img', 'bgimg']) if (q.get(k) && !/^(https?:|\/abs\/)/.test(q.get(k))) q.set(k, '/abs/' + path.resolve(q.get(k)).replace(/\\/g, '/'));
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  let err = null; page.on('pageerror', e => { err = e; });
  await page.goto(`http://127.0.0.1:${port}/templates/${template}?${q}`);
  await page.waitForFunction(() => window.READY === true, null, { timeout: 60000 });
  if (err) throw err;
  if (still !== null) {
    await page.evaluate(t => window.render(t), still);
    await page.screenshot({ path: stillOut || out.replace(/\.\w+$/, '.png'), omitBackground: true });
  } else {
    // opaque backgrounds -> near-lossless H.264 (small, fast to seek); graphics with alpha -> qtrle
    const enc = opaque ? ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '12', '-g', '30', '-pix_fmt', 'yuv420p']
                       : ['-c:v', 'qtrle', '-pix_fmt', 'argb'];
    const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', opaque ? 'mjpeg' : 'png', '-i', '-', ...enc, out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const done = new Promise(r => ff.on('close', r));
    const n = Math.round(dur * fps); let prevSig = null, prevBuf = null, shots = 0;
    for (let i = 0; i < n; i++) {
      const sig = await page.evaluate(t => { window.render(t); const s = document.getElementById('s'); return s ? s.innerHTML : null; }, i / fps);
      let buf;
      if (sig !== null && sig === prevSig) buf = prevBuf;                 // nothing moved: reuse the last frame
      else { buf = opaque ? await page.screenshot({ type: 'jpeg', quality: 95 }) : await page.screenshot({ omitBackground: true, type: 'png' }); shots++; }
      prevSig = sig; prevBuf = buf;
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    }
    ff.stdin.end(); await done;
    if (process.env.GFX_VERBOSE) console.error(`  ${path.basename(out)}: ${shots}/${n} frames captured`);
  }
  await page.close();
  return out;
}

try {
  if (a[0] === '--batch') {
    const jobs = JSON.parse(fs.readFileSync(a[1], 'utf8')); const workers = +opt('workers', 3);
    let next = 0;
    await Promise.all(Array.from({ length: Math.min(workers, jobs.length) }, async () => {
      while (next < jobs.length) { const j = jobs[next++]; await job(j); console.log(j.out); }
    }));
  } else {
    const [out, qs] = a;
    if (!out || qs === undefined) { console.error(`usage: node render_gfx.mjs out.mov '{"type":"title",...}' --w 1080 --h 864 --dur 2.5 | --batch jobs.json`); process.exit(1); }
    const params = fs.existsSync(qs) ? JSON.parse(fs.readFileSync(qs, 'utf8')) : JSON.parse(qs);
    const si = a.indexOf('--still');
    await job({ out, params, w: +opt('w', 1080), h: +opt('h', 864), dur: +opt('dur', 2.5), template: opt('template', 'gfx.html'),
                still: si >= 0 ? +a[si + 1] : null, stillOut: si >= 0 ? a[si + 2] : null });
    console.log(out);
  }
} catch (e) { console.error('render error:', e.message || e); process.exitCode = 1; }
await browser.close(); srv.close();
