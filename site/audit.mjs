import { chromium } from 'playwright';
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
const p = await b.newPage({ viewport: { width: 1400, height: 1000 } });
const errs = [];
p.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
p.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE: ' + m.text()); });
await p.goto('http://localhost:8795/', { waitUntil: 'networkidle' });

const chipState = async () => p.$$eval('.chip[data-filter="art"]',
  els => els.map(e => ({ label: e.textContent.trim(), value: e.dataset.value, on: e.classList.contains('on'), checked: e.getAttribute('aria-checked') })));

const visible = async () => p.$$eval('#panel-upcoming .card, #panel-upcoming [data-art]',
  els => els.filter(e => e.offsetParent !== null)
            .map(e => ({ art: e.dataset.art, title: (e.querySelector('h3,h2,.card-title')?.textContent || e.textContent).trim().slice(0, 52) })));

console.log('--- art chips as loaded ---');
console.log(JSON.stringify(await chipState(), null, 1));

const shown = await visible();
console.log(`\n--- visible on load: ${shown.length} ---`);
const byArt = {};
for (const s of shown) byArt[s.art] = (byArt[s.art] || 0) + 1;
console.log('by art:', JSON.stringify(byArt));
for (const s of shown) console.log(`  ${s.art} | ${s.title}`);

console.log('\n--- counter says ---');
console.log(await p.$eval('#shown-count', e => e.textContent).catch(() => 'no #shown-count'));

if (errs.length) console.log('\n--- JS ERRORS ---\n' + errs.join('\n'));
else console.log('\nno JS errors');
await b.close();
