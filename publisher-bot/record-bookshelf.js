const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ storageState: 'auth.json' });
  const page = await context.newPage();

  await page.goto('https://kdp.amazon.com/en_US/bookshelf');

  // This opens the Playwright Inspector so you can click around
  // and see the code generated for your actions.
  await page.pause();

  await browser.close();
})();
