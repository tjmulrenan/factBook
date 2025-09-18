// ---- constants ----
// You can override the folder in one run with:  $env:FINAL_DIR='C:\path\to\FINAL
const BASE_FINAL_DIR =
  process.env.FINAL_DIR ?? 'C:\\Users\\timmu\\Documents\\repos\\Factbook Project\\FINAL';

const SERIES_RESULT_ID = 'TEWDPW65QXM'; // only if you use the series step
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

function ts() {
  return new Date().toLocaleTimeString();
}
function log(...args) {
  console.log(`[${ts()}]`, ...args);
}

// waits
async function waitVisible(page, selector, label = selector) {
  log(`WAIT visible → ${label}`);
  await page.waitForSelector(selector, { state: 'visible', timeout: 0 });
}
async function waitHidden(page, selector, label = selector) {
  log(`WAIT hidden → ${label}`);
  await page.waitForSelector(selector, { state: 'hidden', timeout: 0 });
}
async function waitCalm(page) {
  log('WAIT network idle…');
  await page.waitForLoadState('networkidle', { timeout: 0 });
  await page.waitForTimeout(200);
  log('…network idle OK');
}

async function waitReady(page, locator, label = '') {
  const name = label || locator.toString();
  log(`WAIT ready → ${name}`);
  await locator.waitFor({ state: 'visible', timeout: 0 });
  await expect(locator).toBeEnabled({ timeout: 0 });
}

async function ensureVisible(locator) {
  try {
    await locator.scrollIntoViewIfNeeded();
  } catch {}
  await locator.waitFor({ state: 'visible', timeout: 0 });
}

async function clickWhenReady(page, locator, label = '') {
  const name = label || locator.toString();
  log(`CLICK → ${name}`);
  await ensureVisible(locator);
  await expect(locator).toBeEnabled({ timeout: 0 });
  // Guard against overlay/rerender
  await locator.click({ trial: true }).catch(() => {});
  await locator.click();
  // Don’t rely only on networkidle; give the UI a beat to render
  await page.waitForTimeout(300);
}

async function fillWhenReady(page, locator, value, label = '') {
  const name = label || locator.toString();
  await waitReady(page, locator, name);
  log(`FILL → ${name} = ${JSON.stringify(value).slice(0, 120)}`);
  await locator.fill(value);
  await waitCalm(page);
}

async function setFilesWhenReady(page, locator, files, label = '') {
  const name = label || locator.toString();
  await waitReady(page, locator, name);
  log(`UPLOAD → ${name} = ${Array.isArray(files) ? files.join(', ') : files}`);
  await locator.setInputFiles(files);
  await waitCalm(page);
}

// ---- date & text helpers ----
const LEAP_YEAR = 2024; // keep using a leap year so DOY 366 works

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

function doyToMonthDay(doy, year = LEAP_YEAR) {
  const d = new Date(Date.UTC(year, 0, 1));
  d.setUTCDate(doy);
  return { monthName: MONTHS[d.getUTCMonth()], day: d.getUTCDate() };
}
function ordinal(n) {
  const s = ['th', 'st', 'nd', 'rd'],
    v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}
function zodiac(monthName, day) {
  const mm = MONTHS.indexOf(monthName) + 1;
  const v = mm * 100 + day;
  const ranges = [
    ['Capricorn', 1222, 119],
    ['Aquarius', 120, 218],
    ['Pisces', 219, 320],
    ['Aries', 321, 419],
    ['Taurus', 420, 520],
    ['Gemini', 521, 620],
    ['Cancer', 621, 722],
    ['Leo', 723, 822],
    ['Virgo', 823, 922],
    ['Libra', 923, 1022],
    ['Scorpio', 1023, 1121],
    ['Sagittarius', 1122, 1221],
  ];
  for (const [name, start, end] of ranges) {
    if (start <= end ? v >= start && v <= end : v >= start || v <= end) return name;
  }
  return 'Unknown';
}
function buildKeywords(monthName, day, sign) {
  const m = monthName.toLowerCase();
  return `${m} ${day} ${m} ${ordinal(day).toLowerCase()} ${day} ${m} ${sign.toLowerCase()}`;
}

// ---------------- TEST ----------------
test('publish paperback from DOY', async ({ page }) => {
  page.setDefaultTimeout(0);
  page.setDefaultNavigationTimeout(0);

  // optional: log browser events
  page.on('console', (msg) => log(`BROWSER [${msg.type()}]`, msg.text()));
  page.on('request', (req) => log('REQUEST →', req.method(), req.url()));
  page.on('response', (res) => log('RESPONSE ←', res.status(), res.url()));

  // ---- read DOY and derive title/paths/keywords ----
  const doyRaw = process.env.DOY ?? '292'; // use env var if set, else "284"
  const doy = Number(doyRaw);
  log(`DOY: ${doy} (source: ${process.env.DOY ? 'ENV' : 'DEFAULT'})`);
  if (!Number.isInteger(doy) || doy < 1 || doy > 366) {
    throw new Error(`Bad DOY: ${doyRaw}`);
  }

  const { monthName, day } = doyToMonthDay(doy);
  const title = `${monthName} ${day}`;
  const sign = zodiac(monthName, day);
  const keywords0 = buildKeywords(monthName, day, sign);

  const folder = `${doy}_${monthName}_${day}`;
  const folderPath = path.join(BASE_FINAL_DIR, folder);
  const manuscriptPath = path.join(folderPath, 'full_manuscript.pdf');
  const coverPath = path.join(folderPath, 'book_cover.pdf');

  if (!fs.existsSync(manuscriptPath)) throw new Error(`Missing manuscript:\n${manuscriptPath}`);
  if (!fs.existsSync(coverPath)) throw new Error(`Missing cover:\n${coverPath}`);

  log('DOY:', doy);
  log('Title:', title);
  log('Sign:', sign);
  log('Keywords0:', keywords0);
  log('Manuscript:', manuscriptPath);
  log('Cover:', coverPath);

  // ---- start ----
  await page.goto('https://kdp.amazon.com/en_US/bookshelf', { waitUntil: 'networkidle' });
  await waitCalm(page);

  //   // Create new title → paperback
  //   await clickWhenReady(page, page.getByRole('link', { name: '+ Create new title or series' }), 'Create new title');
  //   await clickWhenReady(page, page.getByRole('button', { name: 'Create paperback' }), 'Create paperback');

  //   // Title & subtitle
  //   await fillWhenReady(page, page.locator('#data-print-book-title'), title, 'Book title');
  //   await fillWhenReady(
  //     page,
  //     page.locator('#data-print-book-subtitle'),
  //     'Amazing stories and brain-teasing puzzles from one unforgettable day in history — perfect for curious minds of all ages.',
  //     'Subtitle'
  //   );

  //   // Rights / age etc.
  //   await clickWhenReady(page, page.getByRole('radio', { name: 'I own the copyright and I' }), 'Rights: I own');
  //   await clickWhenReady(page, page.locator('#data-print-book-is-adult-content label:has-text("No")'), 'Adult content: No');

  //   // Keywords (slot 0 comes from the DOY; fill the rest with your preferred tags)
  //   const moreKeywords = [
  //     'daily history facts',
  //     'brain teasers',
  //     'fun facts book',
  //     'puzzle book for adults',
  //     'facts for kids 8-12',
  //     'today in history'
  //   ];

  //   const kwAll = [keywords0, ...moreKeywords].slice(0, 7);
  //   for (let i = 0; i < kwAll.length; i++) {
  //     await fillWhenReady(page, page.locator(`#data-print-book-keywords-${i}`), kwAll[i], `Keywords slot ${i}`);
  // }

  await page.goto('https://kdp.amazon.com/en_US/title-setup/paperback/07PM9X7BJJG/details', {
    waitUntil: 'networkidle',
  });

  // Open the series modal
  await clickWhenReady(
    page,
    page.locator('[data-test-id="add-series-details-button"]'),
    'Add to series',
  );

  // Wait for the modal
  const seriesDialog = page.getByRole('dialog', { name: /Add title to a series/i });
  await seriesDialog.waitFor({ state: 'visible' });

  // Select existing series
  const selectExisting = seriesDialog.getByRole('button', { name: /^Select series$/ });
  await clickWhenReady(page, selectExisting, 'Select series');

  // 🔎 Pick the first available series row instead of a hard-coded ID
  const seriesRow = seriesDialog.locator('[data-test-id^="series-search-result"]').first();
  await expect(seriesRow).toBeVisible();
  await clickWhenReady(page, seriesRow, 'First series row');

  // Choose relation
  const relationDialog = page.getByRole('dialog', { name: /How is this title related/i });
  await relationDialog.waitFor({ state: 'visible' });

  const mainBtn = relationDialog.locator('[data-test-id="modal-button-main"]');
  await clickWhenReady(page, mainBtn, 'Main content');

  // Confirm/continue (some accounts show an extra confirm)
  const publishBtn = relationDialog.locator('[data-test-id="modal-button-publish"]');
  if (await publishBtn.isVisible().catch(() => false)) {
    await clickWhenReady(page, publishBtn, 'Confirm and continue');
  }

  // Final submit if present
  const submitBtn = page.getByRole('button', { name: /^Submit$/ });
  if (await submitBtn.isVisible().catch(() => false)) {
    await clickWhenReady(page, submitBtn, 'Submit');
  }

  // Continue to Content
  await clickWhenReady(
    page,
    page.getByRole('button', { name: 'Save and Continue' }),
    'Save & Continue (Details)',
  );

  // Content choices
  await clickWhenReady(page, page.getByRole('button', { name: 'Assign ISBN' }), 'Assign ISBN');
  await clickWhenReady(
    page,
    page.getByRole('button', { name: 'Standard color interior with' }),
    'Interior: Standard color',
  );
  await clickWhenReady(page, page.getByRole('button', { name: 'Bleed (PDF only)' }), 'Bleed: On');
  await clickWhenReady(page, page.getByRole('button', { name: 'Glossy' }), 'Cover finish: Glossy');

  // Upload manuscript
  await setFilesWhenReady(
    page,
    page.getByRole('button', { name: 'Upload manuscript' }),
    manuscriptPath,
    'Upload manuscript',
  );
  await waitHidden(page, 'text=/Uploading|Processing manuscript/i', 'Manuscript processing');
  await waitVisible(page, 'text=/Upload complete|Manuscript uploaded|✓/i', 'Manuscript uploaded');
  await waitCalm(page);

  // Upload cover
  await clickWhenReady(
    page,
    page.getByRole('link', { name: 'Upload a cover you already' }),
    'Upload cover link',
  );
  await clickWhenReady(
    page,
    page.getByRole('button', { name: 'Upload your cover file' }),
    'Upload cover button',
  );
  await setFilesWhenReady(
    page,
    page.getByRole('button', { name: 'Upload your cover file' }),
    coverPath,
    'Upload cover',
  );
  await waitHidden(page, 'text=/Uploading|Processing cover/i', 'Cover processing');
  await waitVisible(page, 'text=/Upload complete|Cover uploaded|✓/i', 'Cover uploaded');
  await waitCalm(page);

  // AI declarations
  await clickWhenReady(page, page.getByRole('link', { name: 'Yes' }), 'AI Declarations: Yes');
  await clickWhenReady(
    page,
    page.getByLabel('Texts', { exact: true }).locator('span').nth(2),
    'AI Texts toggle',
  );
  await clickWhenReady(
    page,
    page.getByLabel('Some sections, with extensive'),
    'AI Texts: Some sections',
  );
  await fillWhenReady(page, page.getByPlaceholder('e.g. ChatGPT'), 'Claude', 'AI Texts tool');

  await clickWhenReady(
    page,
    page.getByLabel('Images', { exact: true }).locator('span').nth(2),
    'AI Images toggle',
  );
  await clickWhenReady(
    page,
    page.getByLabel('Many AI-generated images, with minimal or no editing'),
    'AI Images: Many',
  );
  await fillWhenReady(page, page.getByPlaceholder('e.g. DALL-E'), 'ChatGPT', 'AI Images tool');

  await clickWhenReady(
    page,
    page.getByLabel('Translations', { exact: true }).locator('span').nth(2),
    'AI Translations toggle',
  );
  await clickWhenReady(page, page.getByLabel('None'), 'AI Translations: None');

  // Save & preview (can take ages)
  await clickWhenReady(
    page,
    page.getByRole('button', { name: 'Save and Continue' }),
    'Save & Continue (Content)',
  );
  await waitHidden(
    page,
    'text=/Preparing your files|Processing|Generating preview/i',
    'Previewer processing',
  );
  await waitVisible(page, 'role=link[name="Approve"]', 'Approve link visible');
  await clickWhenReady(page, page.getByRole('link', { name: 'Approve' }), 'Approve preview');

  // (Optional) publish…
  // await clickWhenReady(page, page.getByRole('button', { name: 'Publish Your Paperback Book' }), 'Publish');

  page, 'role=link[name="Approve"]', 'Approve link visible';
  await clickWhenReady(page, page.getByRole('link', { name: 'Approve' }), 'Approve preview');

  // (Optional) publish…
  // await clickWhenReady(page, page.getByRole('button', { name: 'Publish Your Paperback Book' }), 'Publish');
});
