// Пакетний рендер кадрів: node render.js shots.json outdir
// Кожен кадр — окрема сторінка з window.SHOT; Chromium headless + SwiftShader WebGL.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = __dirname;
const shotsFile = process.argv[2];
const outDir = process.argv[3];
const only = process.argv[4];
const shots = JSON.parse(fs.readFileSync(shotsFile, 'utf8'));
const glbDir = path.dirname(path.resolve(shotsFile));

const types = { '.html': 'text/html', '.js': 'text/javascript', '.glb': 'model/gltf-binary', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  let u = decodeURIComponent(req.url.split('?')[0]);
  let f = u.startsWith('/glb/') ? path.join(glbDir, u.slice(5)) : path.join(ROOT, u);
  fs.readFile(f, (err, data) => {
    if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': types[path.extname(f)] || 'application/octet-stream' });
    res.end(data);
  });
});

(async () => {
  await new Promise(r => server.listen(0, r));
  const port = server.address().port;
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  fs.mkdirSync(outDir, { recursive: true });
  for (const s of shots) {
    if (only && !s.out.includes(only)) continue;
    const page = await browser.newPage({ viewport: { width: s.w || 1600, height: s.h || 1200 } });
    page.on('console', m => { if (m.type() === 'error') console.log('console:', m.text()); });
    page.on('pageerror', e => console.log('pageerror:', e.message));
    const shot = { ...s, glb: `/glb/${s.glb}` };
    await page.addInitScript(`window.SHOT = ${JSON.stringify(shot)};`);
    await page.goto(`http://127.0.0.1:${port}/render.html`);
    await page.waitForFunction('window.__done === true', null, { timeout: 240000 });
    const canvas = await page.$('canvas');
    await canvas.screenshot({ path: path.join(outDir, s.out) });
    console.log('rendered', s.out);
    await page.close();
  }
  await browser.close();
  server.close();
})().catch(e => { console.error(e); process.exit(1); });
