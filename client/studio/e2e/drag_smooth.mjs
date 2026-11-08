// Use a disposable local Studio with a fresh samples/build_reference.py project.
// VT_URL=http://127.0.0.1:5177 node e2e/drag_smooth.mjs [screenshot folder]
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { chromium } from 'playwright-core';
import { chromePath } from './common.mjs';

const studio = new URL(process.env.VT_URL ?? 'http://127.0.0.1:5177');
assert(['127.0.0.1', 'localhost', '[::1]'].includes(studio.hostname), 'Run this write test on a disposable loopback Studio.');
const project = process.env.VT_PROJECT ?? 'reference';
const projectPath = `/api/projects/${encodeURIComponent(project)}`;
const scenePath = `${projectPath}/scenes/s1`;
const out = process.argv[2] ?? fs.mkdtempSync(path.join(os.tmpdir(), 'vt-drag-smooth-'));
fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch({ executablePath: chromePath(), args: ['--disable-gpu'] });
const context = await browser.newContext({ viewport: { width: 1500, height: 950 } });
const page = await context.newPage();
page.setDefaultTimeout(10000);
const errors = [];
let saves = 0;
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => {
  if (request.method() === 'PATCH' && new URL(request.url()).pathname === scenePath) saves++;
});
// The real composition is loaded from scratch. Thumbnails are outside this test.
await context.route('**/thumbnails?*', route => route.request().method() === 'POST'
  ? route.fulfill({ json: { status: 'skipped' } }) : route.continue());

await context.addInitScript(() => {
  if (window === window.parent) {
    window.dragMoves = 0;
    window.dragRect = null;
    window.addEventListener('pointermove', event => { if (event.buttons === 1) window.dragMoves++; }, true);
    window.addEventListener('message', event => {
      if (event.data?.vt === 'rect') window.dragRect = event.data;
    });
    return;
  }
  const probe = window.dragProbe = { full: 0, look: 0, intervals: [], start: false };
  window.addEventListener('message', event => {
    if (event.source !== window.parent) return;
    if (event.data?.vt === 'data') probe.full++;
    if (event.data?.vt === 'look') probe.look++;
  });
  let last = null;
  const measure = now => {
    if (probe.start && last !== null) probe.intervals.push(now - last);
    last = probe.start ? now : null;
    requestAnimationFrame(measure);
  };
  requestAnimationFrame(measure);
});

const readPlan = async () => {
  const response = await context.request.get(new URL(`${projectPath}/scenes`, studio).href);
  assert.equal(response.status(), 200);
  return response.json();
};
const point = async locator => {
  const box = await locator.boundingBox();
  assert(box, `Visible control missing: ${locator}`);
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
};
const shot = name => page.screenshot({ path: path.join(out, `${name}.png`), animations: 'disabled' });

try {
  const initial = await readPlan();
  const scene = initial.plan.scenes.find(scene => scene.id === 's1');
  const icon = scene?.elements[1];
  assert(icon?.type === 'icon' && icon.x == null && icon.y == null && !icon.keyframes?.length,
    'This test needs the fresh automatically laid out icon in the reference project.');
  assert(scene.elements.length >= 2, 'The fixture must exercise a scene with several visuals.');

  await page.goto(new URL(`/p/${encodeURIComponent(project)}/pro`, studio).href, { waitUntil: 'domcontentloaded' });
  await page.locator('.scene-card').first().waitFor();
  await page.locator('.scene-card').first().click();
  const frame = await (await page.locator('iframe[title="Video preview"]').elementHandle()).contentFrame();
  assert(frame, 'Preview iframe opened.');
  await frame.waitForFunction(() => typeof window.__vtFree?.natural === 'function' && window.dragProbe.full > 0);
  const timing = initial.timing.scenes.find(scene => scene.id === 's1');
  const seekTo = (timing.end - 0.15).toFixed(2);
  await page.getByRole('slider', { name: 'Seek' }).fill(seekTo);
  await frame.waitForFunction(time => Math.abs(window.__vt.timeline().time() - time) < .02, Number(seekTo));
  const rendered = frame.locator('.scene[data-scene="s1"] .el[data-el="1"]').first();
  await rendered.waitFor({ state: 'visible' });
  const pick = await point(rendered);
  await page.mouse.click(pick.x, pick.y);
  await page.getByTestId('transform-handles').waitFor();
  await page.waitForFunction(() => window.dragRect?.scene === 's1' && window.dragRect.index === 1 && !window.dragRect.free);
  const before = await page.evaluate(() => window.dragRect);
  assert(before.natural?.[0] > 0 && before.box?.[2] > 0, `The preview measured the automatic and natural sizes: ${JSON.stringify(before)}`);
  await shot('before');

  const move = await point(page.getByTestId('handle-move'));
  await page.mouse.move(move.x, move.y);
  await page.mouse.down();
  await page.evaluate(() => { window.dragMoves = 0; });
  await frame.evaluate(() => Object.assign(window.dragProbe, { full: 0, look: 0, intervals: [], start: true }));
  await page.mouse.move(move.x + 2, move.y + 1);
  await page.waitForFunction(() => window.dragRect?.free);
  const afterFirst = await page.evaluate(() => window.dragRect.box);
  const firstWidthChange = Math.abs(afterFirst[2] / before.box[2] - 1);
  await frame.evaluate(() => { window.dragProbe.start = false; });
  await shot('during');

  // A pause during a held drag must not save or reload the server's composition.
  await page.waitForTimeout(650);
  await frame.evaluate(() => { window.dragProbe.start = true; });
  await page.mouse.move(move.x + 38, move.y + 13, { steps: 59 });
  await page.waitForFunction(() => window.dragRect?.box?.[0] > 0 && window.dragMoves >= 60);
  const during = await frame.evaluate(() => {
    const probe = window.dragProbe;
    probe.start = false;
    const intervals = [...probe.intervals].sort((a, b) => a - b);
    return { full: probe.full, look: probe.look, frames: intervals.length,
      medianMs: intervals[Math.floor(intervals.length / 2)], p95Ms: intervals[Math.floor(intervals.length * .95)] };
  });
  const moves = await page.evaluate(() => window.dragMoves);
  const heldSaves = saves;
  const heldRect = await page.evaluate(() => window.dragRect.box);

  const response = page.waitForResponse(response => response.request().method() === 'PATCH'
    && new URL(response.url()).pathname === scenePath);
  await page.mouse.up();
  assert((await response).ok(), 'Scratch server accepts the drag on release.');
  const saved = (await readPlan()).plan.scenes.find(scene => scene.id === 's1').elements[1];
  const phone = await page.locator('.phone').boundingBox();
  assert(Math.abs(saved.x - ((before.box[0] + before.box[2] / 2) / before.frame[0] + 38 / phone.width)) < .01,
    'The saved horizontal position follows the release point.');
  assert(Math.abs(saved.y - ((before.box[1] + before.box[3] / 2) / before.frame[1] + 13 / phone.height)) < .01,
    'The saved vertical position follows the release point.');
  await frame.waitForFunction(({ x, y }) => {
    const position = document.querySelector('.scene[data-scene="s1"] .el[data-el="1"]')?.closest('.free-position');
    return position && Math.abs(parseFloat(position.style.left) - x * 100) < .1
      && Math.abs(parseFloat(position.style.top) - y * 100) < .1;
  }, { x: saved.x, y: saved.y });
  await shot('after');

  const metrics = { moves, ...during, widthBefore: before.box[2], widthAfterFirstMove: afterFirst[2],
    naturalWidth: before.natural[0], firstWidthChangePct: firstWidthChange * 100, heldSaves };
  console.log(JSON.stringify(metrics, null, 2));
  assert.equal(moves, 60, 'Measured the requested number of pointer moves.');
  assert(firstWidthChange < .05, 'The icon keeps its width within 5% on the first move.');
  assert(during.full <= 2, 'At most two full composition messages arrive during the drag.');
  assert(during.look >= 30, 'The fixture exercised frequent live element updates.');
  assert(during.frames >= 30 && during.medianMs <= 17.2, 'Median frame cadence remains near 60 Hz in software Chrome.');
  assert.equal(heldSaves, 0, 'A paused pointer does not save before release.');
  assert(heldRect[0] - before.box[0] > 30, 'The icon actually moved on the canvas before release.');

  assert.deepEqual(errors, []);
  console.log(`Drag cadence, takeover and release passed. Screenshots: ${out}`);
} catch (error) {
  await shot('failure').catch(() => {});
  console.error(`Drag test failed. Screenshots: ${out}`);
  throw error;
} finally {
  await browser.close();
}
