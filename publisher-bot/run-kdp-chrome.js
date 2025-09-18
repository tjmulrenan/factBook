const { chromium } = require('playwright');
const path = require('path');
const readline = require('readline');

function waitForEnter(prompt) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) =>
    rl.question(prompt, (ans) => {
      rl.close();
      resolve(ans);
    }),
  );
}

(async () => {
  try {
    // Path to your Chrome "Default" profile
    const userDataDir = path.join(process.env.LOCALAPPDATA, 'Google\\Chrome\\User Data\\Default');

    console.log('👉 Make sure Chrome is completely CLOSED before running this.');
    console.log('Launching Chrome with your live Default profile...');

    const context = await chromium.launchPersistentContext(userDataDir, {
      channel: 'chrome', // use your installed Chrome
      headless: false, // headed mode (visible window)
      viewport: null,
      args: ['--start-maximized'],
    });

    const page = context.pages()[0] || (await context.newPage());

    // Go to your KDP Bookshelf
    await page.goto('https://kdp.amazon.com/en_US/bookshelf', { waitUntil: 'networkidle' });

    console.log('\n✅ Chrome launched with your Default profile.');
    console.log('If Amazon asks for 2FA, complete it in the window.');
    console.log(
      'When you’re on the Bookshelf, return to this terminal and press Enter to save your session.',
    );

    await waitForEnter('Press Enter to save auth.json and close the browser...');

    // Save cookies/session to auth.json
    await context.storageState({ path: 'auth.json' });
    console.log('💾 Saved auth.json — you can now run future scripts without 2FA.');

    await context.close();
    console.log('✅ Done. You can reopen Chrome normally now.');
  } catch (err) {
    console.error('ERROR:', err);
    process.exit(1);
  }
})();
