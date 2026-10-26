const puppeteer = require('puppeteer-core');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1400,900'],
    defaultViewport: { width: 1400, height: 900 },
  });

  const page = await browser.newPage();

  // 1. Go to the app - redirects to /login (or /setup)
  await page.goto('http://localhost:8000', { waitUntil: 'networkidle0', timeout: 30000 });

  // 2. Check if we need to login
  const url = page.url();
  console.log('landed on:', url);

  if (url.includes('/login')) {
    await page.waitForSelector('input[id="username"], input[name="username"]', { timeout: 10000 });
    const inputs = await page.$$('input');
    // First input = username, second = password
    if (inputs.length >= 2) {
      await inputs[0].type('apitest');
      await inputs[1].type('admin123');
      const buttons = await page.$$('button[type="submit"], form button:not([type="button"])');
      if (buttons.length > 0) {
        await buttons[0].click();
      }
    }
    await page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 15000 }).catch(() => {});
  }

  console.log('after login:', page.url());

  // 3. Wait for the dashboard to render
  await page.waitForSelector('[role="tablist"]', { timeout: 15000 });
  await new Promise(r => setTimeout(r, 2000)); // let data load

  // 4. Click the "Stock dynamics" tab
  const tabs = await page.$$('[role="tab"]');
  console.log('tabs found:', tabs.length);
  for (const tab of tabs) {
    const text = await page.evaluate(el => el.textContent, tab);
    console.log('  tab:', text);
    if (text.includes('Stock dynamics')) {
      await tab.click();
      break;
    }
  }

  // 5. Wait for the dynamics content (chart or KPI strip)
  await new Promise(r => setTimeout(r, 3000)); // chart animation

  // 6. Screenshot
  await page.screenshot({
    path: 'stock_dynamics.png',
    fullPage: false,
    type: 'png',
  });
  console.log('screenshot saved: stock_dynamics.png');

  // Also grab the "Top movers" sub-view
  const subButtons = await page.$$('button');
  for (const btn of subButtons) {
    const text = await page.evaluate(el => el.textContent, btn);
    if (text === 'Top movers') {
      await btn.click();
      await new Promise(r => setTimeout(r, 1500));
      await page.screenshot({ path: 'stock_dynamics_top.png', type: 'png' });
      console.log('screenshot saved: stock_dynamics_top.png');
      break;
    }
  }

  // And "Daily detail"
  for (const btn of await page.$$('button')) {
    const text = await page.evaluate(el => el.textContent, btn);
    if (text === 'Daily detail') {
      await btn.click();
      await new Promise(r => setTimeout(r, 1500));
      await page.screenshot({ path: 'stock_dynamics_daily.png', type: 'png' });
      console.log('screenshot saved: stock_dynamics_daily.png');
      break;
    }
  }

  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });