// make_docs_shots.mjs - screenshots of the edit page for the README (docs/img). Face-free on purpose:
// only the picker, the steps, the timeline and the graphics are captured - never the video player or the transcript.
//   node make_docs_shots.mjs <out dir> <picker page url> <finished-edit page url>
import { chromium } from 'playwright-core';
import path from 'node:path'; import fs from 'node:fs';
const [out, pickerUrl, doneUrl] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ args: ['--force-color-profile=srgb'] });
const page = await browser.newPage({ viewport: { width: 1000, height: 1400 }, deviceScaleFactor: 1.5 });
const wait = ms => new Promise(r => setTimeout(r, ms));

await page.goto(pickerUrl); await wait(2500);
await page.locator('#choose').screenshot({ path: path.join(out, 'page_choose.png') });
console.log('page_choose.png');

await page.goto(doneUrl); await wait(9000);          // thumbnails of the graphics are made on first request
await page.locator('.grid > .card').first().screenshot({ path: path.join(out, 'page_steps.png') });
await page.locator('#tl').locator('xpath=..').screenshot({ path: path.join(out, 'page_timeline.png') });
await page.locator('#gfx').locator('xpath=..').screenshot({ path: path.join(out, 'page_graphics.png') });
await page.locator('#chosen').screenshot({ path: path.join(out, 'page_choice.png') });
console.log('page_steps.png page_timeline.png page_graphics.png page_choice.png');
await browser.close();
