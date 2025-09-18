// run-with-doy.js
const { spawn } = require('child_process');
const readline = require('readline');
const path = require('path');
const fs = require('fs');

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

rl.question('Enter DOY (1-366): ', (ans) => {
  rl.close();
  const doy = ans.trim();
  if (!/^\d+$/.test(doy) || +doy < 1 || +doy > 366) {
    console.error('Bad DOY. Must be an integer 1–366.');
    process.exit(1);
  }

  const env = { ...process.env, DOY: doy };

  // Ensure spec exists
  const specFs = path.join(process.cwd(), 'tests', 'publish-book.spec.js');
  if (!fs.existsSync(specFs)) {
    console.error(`Spec not found: ${specFs}`);
    process.exit(1);
  }

  // ✅ Call the Playwright CLI JS with Node (no .cmd, no quoting issues)
  const nodeBin = process.execPath; // current node.exe
  const pwCli = require.resolve('@playwright/test/cli'); // Playwright CLI entry

  const args = [pwCli, 'test', 'tests/publish-book.spec.js']; // headed/slowMo from config

  const cp = spawn(nodeBin, args, { stdio: 'inherit', env });
  cp.on('exit', (code) => process.exit(code ?? 1));
  cp.on('error', (err) => {
    console.error('Failed to launch Playwright:', err);
    process.exit(1);
  });
});
