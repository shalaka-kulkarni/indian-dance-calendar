import { chromium } from 'playwright';
const S='/tmp/claude-0/-home-user-skyd-app/ed2bb6ea-ee87-5344-8c43-397ba0ca3569/scratchpad';
const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
const ctx=await b.newContext({colorScheme:'light',viewport:{width:1280,height:600}});
const p=await ctx.newPage();
await p.goto('http://localhost:8768/index.html');
await p.waitForTimeout(400);
await p.screenshot({path:`${S}/hero-linework.png`});
await b.close(); console.log('ok');
