// Запис анімації виготовлення: node record_process.js out.mp4 [fps] [w] [h] [t0] [t1]
//   або пробні кадри: node record_process.js --stills outdir t1,t2,...
// Сторінка viewer/process.html?record — детермінований кадр window.renderAt(t); кадри йдуть у ffmpeg без проміжних файлів.
const http = require('http'), fs = require('fs'), path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('playwright');
const VIEW = path.resolve(__dirname, '..', '..', 'viewer');
const THREE_DIR = process.env.THREE_DIR || path.join(__dirname, 'node_modules', 'three');
const args = process.argv.slice(2);
const stills = args[0] === '--stills';
const out = stills ? args[1] : (args[0] || 'process.mp4');
const fps = stills ? 30 : +(args[1] || 30);
const W = +(stills ? 1280 : (args[2] || 1280)), H = +(stills ? 720 : (args[3] || 720));

const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.txt': 'text/plain' };
const srv = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  const f = path.join(VIEW, u === '/' ? 'process.html' : u);
  fs.readFile(f, (e, d) => {
    if (e) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': types[path.extname(f)] || 'application/octet-stream', 'Content-Length': d.length });
    res.end(d);
  });
});

(async () => {
  await new Promise((r) => srv.listen(0, r));
  const port = srv.address().port;
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  const errs = [];
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  page.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
  await page.route('https://cdn.jsdelivr.net/npm/three@0.147.0/**', (route) => {
    const rel = route.request().url().split('three@0.147.0/')[1];
    route.fulfill({ path: path.join(THREE_DIR, rel), contentType: 'text/javascript' });
  });
  await page.route('https://fonts.googleapis.com/**', (r) => r.fulfill({ body: '', contentType: 'text/css' }));
  await page.goto(`http://127.0.0.1:${port}/process.html?record=1`);
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 300000 });
  const TOTAL = await page.evaluate(() => window.TOTAL);
  if (stills) {
    fs.mkdirSync(out, { recursive: true });
    for (const t of args[2].split(',').map(Number)) {
      const t0 = Date.now();
      await page.evaluate((x) => window.renderAt(x), t);
      await page.screenshot({ path: path.join(out, `t${String(t).padStart(6, '0')}.jpg`), type: 'jpeg', quality: 90 });
      console.log('still', t, (Date.now() - t0) + ' ms');
    }
  } else {
    const t0s = +(args[4] || 0), t1s = +(args[5] || TOTAL);
    const n = Math.round((t1s - t0s) * fps);
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const start = Date.now();
    for (let i = 0; i < n; i++) {
      await page.evaluate((x) => window.renderAt(x), t0s + i / fps);
      const buf = await page.screenshot({ type: 'jpeg', quality: 93 });
      if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
      if (i % 150 === 0) console.log(`frame ${i}/${n}  ${((Date.now() - start) / 1000).toFixed(0)} s`);
    }
    ff.stdin.end();
    await new Promise((r) => ff.on('close', r));
    console.log('done', out, ((Date.now() - start) / 1000).toFixed(0) + ' s');
  }
  console.log('errors:', errs.slice(0, 8));
  await browser.close(); srv.close();
})().catch((e) => { console.error(e); process.exit(1); });
