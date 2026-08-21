import { chromium } from 'playwright';
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
const p = await b.newPage({ viewport: { width: 1400, height: 1000 } });
const errs = [];
p.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
p.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE: ' + m.text()); });
const fails = [];
const ok = (cond, msg) => { if (!cond) fails.push(msg); };

await p.goto('http://localhost:8795/', { waitUntil: 'networkidle' });

const vis = () => p.$$eval('#panel-upcoming article.event',
  els => els.filter(e => e.offsetParent !== null).map(e => ({
    art: e.dataset.art, trad: e.dataset.traditions, region: e.dataset.region,
    kind: e.dataset.kind, free: e.dataset.free, presenter: e.dataset.presenter,
    title: e.querySelector('.event-title, h3, h2')?.textContent.trim().slice(0,40) })));
const counter = () => p.$eval('#shown-count', e => +e.textContent);
const clearIfShown = async () => { const btn = await p.$('#clear-filters'); if (btn && await btn.isVisible()) { await btn.click(); await p.waitForTimeout(120); } };
const clickChip = async (f, v) => { await p.click(`.chip[data-filter="${f}"][data-value="${v}"]`); await p.waitForTimeout(80); };

// 1. counter agrees with what is on screen, in every filter state we try
const states = [
  ['art','music'], ['art','dance'],           // music on, dance off -> music only
  ['tradition','classical'], ['tradition','classical'],
  ['region','new_jersey'], ['region','new_jersey'],
  ['kind','community'], ['kind','community'],
];
console.log('--- counter vs DOM across filter states ---');
for (const [f,v] of states) {
  await clickChip(f,v);
  const shown = await vis(), n = await counter();
  ok(shown.length === n, `counter ${n} != visible ${shown.length} after toggling ${f}=${v}`);
  console.log(`  ${f}=${v} -> counter ${n}, dom ${shown.length} ${shown.length===n?'ok':'MISMATCH'}`);
}

// 2. Music alone must contain no dance-only events
await clearIfShown();
await clickChip('art','music'); await clickChip('art','dance');
let shown = await vis();
console.log(`\n--- Music selected: ${shown.length} ---`);
ok(!shown.some(s => s.art === 'dance'), 'a dance-only event is showing under Music');
console.log('  art values present:', [...new Set(shown.map(s=>s.art))].join(', '));

// 3. Dance alone must contain no music-only events
await clickChip('art','dance'); await clickChip('art','music');
shown = await vis();
console.log(`\n--- Dance selected: ${shown.length} ---`);
ok(!shown.some(s => s.art === 'music'), 'a music-only event is showing under Dance');
console.log('  art values present:', [...new Set(shown.map(s=>s.art))].join(', '));

// 4. last art chip cannot be switched off
await clickChip('art','dance');
const artOn = await p.$$eval('.chip[data-filter="art"].on', e => e.length);
ok(artOn >= 1, 'both art chips ended up off, leaving an empty page');
console.log(`\n--- art chips on after trying to turn the last one off: ${artOn} (want >=1) ---`);

// 5. region filter really filters
await clearIfShown();
await clickChip('art','music');
await clickChip('region','new_jersey');
shown = await vis();
ok(shown.every(s => s.region === 'new_jersey'), 'region filter leaked a non-NJ event');
console.log(`\n--- region=new_jersey: ${shown.length}, regions present: ${[...new Set(shown.map(s=>s.region))].join(', ')} ---`);

// 6. greyed-out chips genuinely yield zero
await clearIfShown();
const disabled = await p.$$eval('.chip[aria-disabled="true"]', els => els.map(e => ({f:e.dataset.filter, v:e.dataset.value, n:+e.querySelector('.n')?.textContent})));
console.log(`\n--- greyed-out chips: ${disabled.length} ---`);
for (const d of disabled) { ok(d.n === 0, `chip ${d.f}=${d.v} greyed but count ${d.n}`); }
console.log('  ' + disabled.map(d=>`${d.f}=${d.v}(${d.n})`).join(' ') || '  none');

// 7. Past events tab
await p.click('#tab-past'); await p.waitForTimeout(150);
const past = await p.$$eval('#panel-past article.event', els => els.filter(e=>e.offsetParent!==null).length);
const pastTickets = await p.$$eval('#panel-past a', els => els.filter(a=>/ticket|buy/i.test(a.textContent)).length);
console.log(`\n--- Past events tab: ${past} visible, ${pastTickets} ticket links (want 0) ---`);
ok(past > 0, 'past events tab is empty');
ok(pastTickets === 0, 'past events still show ticket links');

// 8. links sane
await p.click('#tab-upcoming'); await p.waitForTimeout(120);
await clearIfShown();
const links = await p.$$eval('#panel-upcoming a[href]', els => els.map(a => a.getAttribute('href')));
const bad = links.filter(h => !/^https?:\/\//.test(h) && !h.startsWith('/') && !h.startsWith('#'));
console.log(`\n--- ${links.length} links in upcoming; malformed: ${bad.length} ---`);
ok(bad.length === 0, 'malformed hrefs: ' + bad.slice(0,3).join(', '));

console.log('\n=== JS errors: ' + (errs.length || 'none') + ' ===');
errs.forEach(e => console.log('  ' + e));
console.log('\n=== FAILURES: ' + (fails.length || 'none') + ' ===');
fails.forEach(f => console.log('  ✗ ' + f));
await b.close();
