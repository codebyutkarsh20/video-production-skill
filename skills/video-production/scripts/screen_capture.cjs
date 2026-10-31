// Playwright capture helpers for sharp, cursor-visible walkthroughs. Playwright comes from the host project.
//
//   const {installCursor, recordFrames} = require('./screen_capture.cjs');
//   const context = await browser.newContext({viewport: {width: 1280, height: 720}, deviceScaleFactor: 2});
//   await installCursor(context);
//   const page = await context.newPage();
//   const {frames, fps} = await recordFrames(page, 'capture', async () => { /* drive the page */ });
//   // ffmpeg -f concat -safe 0 -i capture/frames.ffconcat -vf fps=30,format=yuv420p -c:v libx264 -crf 16 capture.mp4
const fs = require('node:fs');
const path = require('node:path');

// Headless recordings show no system pointer, so the page draws one that follows real mouse events.
function cursorScript() {
  const add = () => {
    if (document.getElementById('__capture_cursor')) return;
    const c = document.createElement('div');
    c.id = '__capture_cursor';
    c.setAttribute('aria-hidden', 'true');
    c.style.cssText = 'position:fixed;left:-40px;top:-40px;width:24px;height:24px;z-index:2147483647;pointer-events:none';
    c.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24"><path d="M4 2l15 12-7 1 4 7-3 1-4-7-5 4z" fill="#111" stroke="#fff" stroke-width="1.5"/></svg>';
    document.documentElement.appendChild(c);
    addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', e => {
      const r = document.createElement('div');
      r.style.cssText = `position:fixed;left:${e.clientX - 18}px;top:${e.clientY - 18}px;width:36px;height:36px;border-radius:50%;border:3px solid rgba(20,120,200,.85);z-index:2147483646;pointer-events:none;transition:transform .35s ease-out,opacity .35s ease-out`;
      document.documentElement.appendChild(r);
      requestAnimationFrame(() => { r.style.transform = 'scale(1.6)'; r.style.opacity = '0'; });
      setTimeout(() => r.remove(), 400);
    }, true);
  };
  if (document.documentElement) add(); else addEventListener('DOMContentLoaded', add);
}

const withCursor = new WeakSet();

async function installCursor(context) {
  withCursor.add(context);
  await context.addInitScript(cursorScript);
}

// Screenshots run in a loop while the action runs, and each frame keeps its real on-screen time.
async function recordFrames(page, dir, action) {
  fs.mkdirSync(dir, {recursive: true});
  const times = [];
  let done = false;
  const cursor = withCursor.has(page.context());
  const loop = (async () => {
    while (!done) {
      // setContent and document.open wipe the overlay without rerunning the init script.
      if (cursor) await page.evaluate(cursorScript).catch(() => {});
      const name = `${String(times.length).padStart(6, '0')}.jpg`;
      await page.screenshot({type: 'jpeg', quality: 95, path: path.join(dir, name)});
      times.push(Date.now());
    }
  })();
  try { await action(); } finally { done = true; await loop; }
  const lines = ['ffconcat version 1.0'];
  times.forEach((t, i) => {
    lines.push(`file ${String(i).padStart(6, '0')}.jpg`);
    lines.push(`duration ${(((times[i + 1] ?? t + 40) - t) / 1000).toFixed(3)}`);
  });
  // The concat demuxer ignores the final duration unless the last file repeats.
  if (times.length) lines.push(`file ${String(times.length - 1).padStart(6, '0')}.jpg`);
  fs.writeFileSync(path.join(dir, 'frames.ffconcat'), lines.join('\n') + '\n');
  const seconds = times.length > 1 ? (times[times.length - 1] - times[0]) / 1000 : 0;
  return {frames: times.length, seconds, fps: seconds ? (times.length - 1) / seconds : 0, concat: path.join(dir, 'frames.ffconcat')};
}

module.exports = {installCursor, recordFrames};
