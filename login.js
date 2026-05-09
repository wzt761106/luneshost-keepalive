const { chromium } = require('playwright-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const axios = require('axios');
chromium.use(StealthPlugin());

const EMAIL          = process.env.LUNESHOST_EMAIL;
const PASSWORD       = process.env.LUNESHOST_PASSWORD;
const TWOCAPTCHA_KEY = process.env.TWOCAPTCHA_KEY;
const SERVER_ID      = '48195';
const LOGIN_URL      = 'https://betadash.lunes.host/login';
const SERVER_URL     = `https://betadash.lunes.host/servers/${SERVER_ID}`;

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function randomDelay(min, max) { return sleep(Math.floor(Math.random() * (max - min) + min)); }

async function solveTurnstile(sitekey, pageUrl) {
  console.log('    提交 Turnstile 到 2Captcha...');
  const submitRes = await axios.post('http://2captcha.com/in.php', null, {
    params: { key: TWOCAPTCHA_KEY, method: 'turnstile', sitekey, pageurl: pageUrl, json: 1 }
  });
  if (submitRes.data.status !== 1) throw new Error(`2Captcha 提交失败: ${JSON.stringify(submitRes.data)}`);
  const id = submitRes.data.request;
  console.log(`    任务 ID: ${id}，等待解答...`);
  for (let i = 0; i < 36; i++) {
    await sleep(5000);
    const res = await axios.get('http://2captcha.com/res.php', {
      params: { key: TWOCAPTCHA_KEY, action: 'get', id, json: 1 }
    });
    if (res.data.status === 1) { console.log(`    解答成功（约 ${(i+1)*5} 秒）`); return res.data.request; }
    if (res.data.request !== 'CAPCHA_NOT_READY') throw new Error(`2Captcha 错误: ${JSON.stringify(res.data)}`);
    console.log(`    等待中... ${(i+1)*5} 秒`);
  }
  throw new Error('Turnstile 解答超时');
}

(async () => {
  console.log('==================================================');
  console.log('  LunesHost 自动登录保活脚本 (Playwright + 2Captcha)');
  console.log('==================================================');

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    locale: 'zh-CN',
  });
  const page = await context.newPage();

  try {
    // 1. 打开登录页
    console.log('[1] 正在打开登录页面...');
    await page.goto(LOGIN_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await randomDelay(2000, 4000);

    // 2. 填写邮箱
    console.log('[2] 正在填写邮箱...');
    await page.fill('input[type="email"], input[name="email"]', EMAIL);
    await randomDelay(800, 1800);

    // 3. 填写密码
    console.log('[3] 正在填写密码...');
    await page.fill('input[type="password"], input[name="password"]', PASSWORD);
    await randomDelay(1000, 2000);

    // 4. 解决 Turnstile
    console.log('[4] 正在解决 Turnstile 验证...');
    const sitekey = await page.evaluate(() => {
      const el = document.querySelector('[data-sitekey], .cf-turnstile, [class*="turnstile"]');
      return el ? (el.getAttribute('data-sitekey') || el.getAttribute('data-cf-sitekey')) : null;
    });
    if (sitekey) {
      console.log(`    Sitekey: ${sitekey}`);
      const token = await solveTurnstile(sitekey, LOGIN_URL);
      // 注入 token 到页面
      await page.evaluate((t) => {
        const inputs = document.querySelectorAll('input[name="cf-turnstile-response"], input[name="g-recaptcha-response"]');
        inputs.forEach(i => i.value = t);
        // 也尝试直接设置 turnstile 的隐藏字段
        const hidden = document.querySelector('input[type="hidden"][name*="turnstile"], input[type="hidden"][name*="cf-"]');
        if (hidden) hidden.value = t;
        // 触发 turnstile callback（如果存在）
        if (window.turnstile && window.turnstile.getResponse) {
          // 已有 response，继续
        }
      }, token);
      console.log('    Token 已注入');
    } else {
      console.log('    未检测到 Turnstile，跳过');
    }
    await randomDelay(1000, 2000);

    // 5. 点击登录
    console.log('[5] 正在点击登录...');
    await page.click('button[type="submit"], input[type="submit"]');
    await page.waitForURL(url => !url.toString().includes('/login'), { timeout: 30000 });
    console.log(`    ✅ 登录成功！当前页面: ${page.url()}`);
    await randomDelay(2000, 4000);

    // 6. 进入服务器页面
    console.log(`[6] 正在进入服务器页面 (ID: ${SERVER_ID})...`);
    try {
      await page.goto(SERVER_URL, { waitUntil: 'load', timeout: 60000 });
    } catch (e) {
    // 超时不要紧，只要页面开始加载就行
      console.log(`    页面加载超时（正常现象），继续停留...`);
    }
    if (page.url().includes('/login')) throw new Error('访问服务器页面被重定向到登录页');
    console.log(`    ✅ 成功进入: ${page.url()}`);

    // 7. 停留 60 秒
    console.log('    开始停留计时...');
    for (let i = 1; i <= 12; i++) {
      await sleep(5000);
      console.log(`    已停留 ${i * 5} / 60 秒`);
    }

    console.log('\n✅ 保活完成！');
  } catch (err) {
    console.error(`\n❌ 出错: ${err.message}`);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
