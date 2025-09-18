// bookshelf.js
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false }); // set true if you want headless
  const context = await browser.newContext({ storageState: 'auth.json' });
  const page = await context.newPage();

  await page.goto('https://kdp.amazon.com/en_US/bookshelf', { waitUntil: 'networkidle' });

  console.log('✅ You should already be logged in and at your Bookshelf.');

  // Example: grab the list of your books
  const titles = await page.locator('.a-link-normal').allInnerTexts();
  console.log('Your bookshelf titles:', titles);

  await browser.close();
})();
