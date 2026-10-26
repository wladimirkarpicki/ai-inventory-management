const puppeteer = require('puppeteer-core');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1400,900'],
    defaultViewport: { width: 1400, height: 900 },
  });

  const page = await browser.newPage();

  // Inject localStorage BEFORE any app script runs: the ThemeProvider reads
  // "ims_theme" on mount and applies the dark class to <html>.
  await page.evaluateOnNewDocument(() => {
    window.localStorage.setItem('ims_theme', 'dark');
  });
  // belt-and-suspenders: also emulate prefers-color-scheme
  await page.emulateMediaFeatures([
    { name: 'prefers-color-scheme', value: 'dark' },
  ]);

  // 1. Go to the app - redirects to /login
  await page.goto('http://localhost:8000', { waitUntil: 'networkidle0', timeout: 30000 });

  // 2. Login
  const url = page.url();
  console.log('landed on:', url);

  if (url.includes('/login')) {
    await page.waitForSelector('input[id="username"], input[name="username"]', { timeout: 10000 });
    const inputs = await page.$$('input');
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

  // Verify dark theme is applied
  const isDark = await page.evaluate(() => document.documentElement.classList.contains('dark'));
  console.log('dark theme applied:', isDark);

  // 3. Wait for the dashboard
  await page.waitForSelector('[role="tablist"]', { timeout: 15000 });
  await new Promise(r => setTimeout(r, 2500)); // data + chart settle

  // 4. Screenshot the dashboard (stat cards + tabs) in dark
  await page.screenshot({ path: 'dashboard_dark.png', type: 'png' });
  console.log('saved: dashboard_dark.png');

  // 5. Click "Stock dynamics"
  for (const tab of await page.$$('[role="tab"]')) {
    const text = await page.evaluate(el => el.textContent, tab);
    if (text.includes('Stock dynamics')) {
      await tab.click();
      break;
    }
  }
  await new Promise(r => setTimeout(r, 3000)); // chart animation

  await page.screenshot({ path: 'stock_dynamics_dark.png', type: 'png' });
  console.log('saved: stock_dynamics_dark.png (Flow)');

  // 6. Top movers sub-view
  for (const btn of await page.$$('button')) {
    const text = await page.evaluate(el => el.textContent, btn);
    if (text === 'Top movers') {
      await btn.click();
      await new Promise(r => setTimeout(r, 1500));
      await page.screenshot({ path: 'stock_dynamics_top_dark.png', type: 'png' });
      console.log('saved: stock_dynamics_top_dark.png');
      break;
    }
  }

  // 7. Daily detail sub-view
  for (const btn of await page.$$('button')) {
    const text = await page.evaluate(el => el.textContent, btn);
    if (text === 'Daily detail') {
      await btn.click();
      await new Promise(r => setTimeout(r, 1500));
      await page.screenshot({ path: 'stock_dynamics_daily_dark.png', type: 'png' });
      console.log('saved: stock_dynamics_daily_dark.png');
      break;
    }
  }

  // 8. Forecast tab (AI badges visible)
  for (const tab of await page.$$('[role="tab"]')) {
    const text = await page.evaluate(el => el.textContent, tab);
    if (text.includes('Forecast')) {
      await tab.click();
      await new Promise(r => setTimeout(r, 2000));
      await page.screenshot({ path: 'forecast_dark.png', type: 'png' });
      console.log('saved: forecast_dark.png');
      break;
    }
  }

  // 9. Orders tab (statuses + overdue)
  for (const tab of await page.$$('[role="tab"]')) {
    const text = await page.evaluate(el => el.textContent, tab);
    if (text.includes('Orders')) {
      await tab.click();
      await new Promise(r => setTimeout(r, 2000));
      await page.screenshot({ path: 'orders_dark.png', type: 'png' });
      console.log('saved: orders_dark.png');
      break;
    }
  }

  // 10. Recommendations (On order column)
  for (const tab of await page.$$('[role="tab"]')) {
    const text = await page.evaluate(el => el.textContent, tab);
    if (text.includes('Recommendations')) {
      await tab.click();
      await new Promise(r => setTimeout(r, 2000));
      await page.screenshot({ path: 'recommendations_dark.png', type: 'png' });
      console.log('saved: recommendations_dark.png');
      break;
    }
  }

  await browser.close();
  console.log('done');
})().catch(err => { console.error(err); process.exit(1); });