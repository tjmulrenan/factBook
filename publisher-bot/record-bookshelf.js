// record-bookshelf.js
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: false }); // visible browser
  const context = await browser.newContext(); // no storageState yet
  const page = await context.newPage();

  // Go to KDP – it will redirect you to login
  await page.goto('https://kdp.amazon.com/en_US/bookshelf', { waitUntil: 'networkidle' });

  console.log('Log in to KDP in the opened window (password, QR/passkey, 2FA, etc).');
  console.log(
    'Once you are fully logged in and can see your Bookshelf, come back here and press Enter.',
  );

  // Wait for you to press Enter in the terminal
  await new Promise((resolve) => process.stdin.once('data', resolve));

  // Save cookies + localStorage into auth.json alongside this file
  const authPath = path.resolve(__dirname, 'auth.json');
  await context.storageState({ path: authPath });
  console.log(`Saved auth state to: ${authPath}`);

  await browser.close();
  process.exit(0);
})();
