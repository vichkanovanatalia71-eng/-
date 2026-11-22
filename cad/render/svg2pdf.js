// node svg2pdf.js <dir> <out.pdf> [pngdir]
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
(async () => {
  const dir = process.argv[2], out = process.argv[3], pngdir = process.argv[4];
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.svg')).sort();
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const pages = files.map(f => `<div class="pg">${fs.readFileSync(path.join(dir, f), 'utf8')}</div>`).join('');
  await page.setContent(`<html><head><style>@page{size:420mm 297mm;margin:0}body{margin:0}.pg{width:420mm;height:297mm;page-break-after:always;overflow:hidden}.pg svg{width:420mm;height:297mm}</style></head><body>${pages}</body></html>`);
  await page.pdf({ path: out, width: '420mm', height: '297mm', printBackground: true });
  if (pngdir) {
    fs.mkdirSync(pngdir, { recursive: true });
    const p2 = await browser.newPage({ viewport: { width: 2380, height: 1684 } });
    for (const f of files) {
      const svg = fs.readFileSync(path.join(dir, f), 'utf8').replace('width="420mm" height="297mm"', 'width="2380" height="1684"');
      await p2.setContent(`<html><body style="margin:0">${svg}</body></html>`);
      await p2.screenshot({ path: path.join(pngdir, f.replace('.svg', '.png')) });
    }
  }
  await browser.close();
  console.log('pdf', out, files.length);
})();
