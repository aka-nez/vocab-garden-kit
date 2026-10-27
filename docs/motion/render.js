const { chromium } = require('playwright');
const fs=require('fs');
(async () => {
  const fps=+process.argv[2]||30; fs.mkdirSync('frames',{recursive:true});
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  await p.goto('file://' + __dirname + '/motion.html'); await p.evaluate(() => document.fonts.ready);
  const D = await p.evaluate(() => window.DURATION); const n=Math.round(D*fps);
  for (let i=0;i<n;i++){ await p.evaluate(t => seek(t), i/fps); await p.screenshot({ path: `frames/f${String(i).padStart(4,'0')}.png` }); }
  console.log('frames',n); await b.close();
})();
