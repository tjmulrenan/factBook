import { defineConfig } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const authPath = path.resolve(__dirname, 'auth.json');

export default defineConfig({
  testDir: 'tests',
  timeout: 3 * 60 * 60 * 1000,
  use: {
    storageState: fs.existsSync(authPath) ? authPath : undefined,
    headless: false,
    launchOptions: { slowMo: 1000 }, // 1s per action (10,000 was 10s)
    actionTimeout: 0,
    navigationTimeout: 0,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  expect: { timeout: 0 },
});
