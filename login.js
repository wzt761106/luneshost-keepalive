const { chromium } = require('playwright');

const EMAIL     = process.env.LUNESHOST_EMAIL;
const PASSWORD  = process.env.LUNESHOST_PASSWORD;
const SERVER_ID = '48195';

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
function randomDelay(minMs, maxMs) {
  return sleep(Math.floor(Math.random() * (maxMs - minMs) + minMs));
}

(async () => {
  console.log('==================================================');
  console.log('  LunesHost 自动登录保活脚本 (Playwright)');
  console.log('==================================================');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    locale: 'zh-CN',
  });
  const page = await context.newPage();

  try {
    // 1. 打开登录页
    console.log('[1] 正在打开登录页面...');
    await page.goto('https://betadash.lunes.host/login', { waitUntil: 'domcontentloaded' });
    await randomDelay(2000, 4000);

    // 2. 填写邮箱
    console.log('[2] 正在填写邮箱...');
    await page.fill('input[type="email"], input[name="email"]', EMAIL);
    await randomDelay(800, 1800);

    // 3. 填写密码
    console.log('[3] 正在填写密码...');
    await page.fill('input[type="password"], input[name="password"]', PASSWORD);
    await randomDelay(1000, 2000);

    // 4. 点击登录
    console.log('[4] 正在点击登录...');
    await page.click('button[type="submit"], input[type="submit"]');
    await page.waitForURL(url => !url.includes('/login'), { timeout: 15000 });
    console.log(`    ✅ 登录成功！当前页面: ${page.url()}`);

    await randomDelay(2000, 4000);

    // 5. 进入服务器页面
    console.log(`[5] 正在进入服务器页面 (ID: ${SERVER_ID})...`);
    await page.goto(`https://betadash.lunes.host/servers/${SERVER_ID}`, { waitUntil: 'domcontentloaded' });
    console.log(`    当前 URL: ${page.url()}`);

    if (page.url().includes('/login')) {
      throw new Error('访问服务器页面被重定向到登录页');
    }
    console.log('    ✅ 成功进入服务器页面，开始停留计时...');

    // 6. 停留 35 秒
    const STAY = 35;
    for (let i = 1; i <= STAY / 5; i++) {
      await sleep(5000);
      console.log(`    已停留 ${i * 5} / ${STAY} 秒`);
    }

    console.log('\n✅ 保活完成！');
  } catch (err) {
    console.error(`\n❌ 出错: ${err.message}`);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
