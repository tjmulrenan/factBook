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
  const doyRaw = process.env.DOY ?? '308'; // use env var if set, else "308"
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

  // Create new title → paperback
  await clickWhenReady(
    page,
    page.getByRole('link', { name: '+ Create new title or series' }),
    'Create new title',
  );
  await clickWhenReady(
    page,
    page.getByRole('button', { name: 'Create paperback' }),
    'Create paperback',
  );

  // Title & subtitle
  await fillWhenReady(page, page.locator('#data-print-book-title'), title, 'Book title');
  await fillWhenReady(
    page,
    page.locator('#data-print-book-subtitle'),
    'Amazing stories and brain-teasing puzzles from one unforgettable day in history — perfect for curious minds of all ages.',
    'Subtitle',
  );

  // Rights / age etc.
  await clickWhenReady(
    page,
    page.getByRole('radio', { name: 'I own the copyright and I' }),
    'Rights: I own',
  );
  await clickWhenReady(
    page,
    page.locator('#data-print-book-is-adult-content label:has-text("No")'),
    'Adult content: No',
  );

  // Keywords (slot 0 comes from the DOY; fill the rest with your preferred tags)
  const moreKeywords = [
    'on this day for kids this day in history',
    'fun facts for kids ages 8 12 general knowledge',
    'inventions for kids explorers for kids',
    'word search for kids crossword puzzles for kids',
    'activity book for kids puzzles',
    'hidden picture find the character puzzle',
  ];

  const kwAll = [keywords0, ...moreKeywords].slice(0, 7);
  for (let i = 0; i < kwAll.length; i++) {
    await fillWhenReady(
      page,
      page.locator(`#data-print-book-keywords-${i}`),
      kwAll[i],
      `Keywords slot ${i}`,
    );
  }

  // await page.goto('https://kdp.amazon.com/en_US/title-setup/paperback/07PM9X7BJJG/details', {
  //   waitUntil: 'networkidle',
  // });

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

  // Click the first available series result button (keep it simple)
  const firstSeriesRow = page.locator('[data-test-id^="series-search-result"]').first();
  await firstSeriesRow.scrollIntoViewIfNeeded();
  await firstSeriesRow.click();

  // Choose relation
  const relationDialog = page.getByRole('dialog');
  await relationDialog.waitFor({ state: 'visible' });

  // Assert and click "Main content"
  const mainBtn = relationDialog.getByRole('button', { name: /Main content/i });
  await expect(mainBtn).toBeVisible();
  await mainBtn.click();

  // Assert and click "Confirm and continue" (if shown)
  const confirmBtn = relationDialog.getByRole('button', { name: /Confirm and continue/i });
  if (await confirmBtn.isVisible().catch(() => false)) {
    await expect(confirmBtn).toBeVisible();
    await confirmBtn.click();
  }

  // Final submit: prefer closing the "saved" popover if it appears;
  // otherwise click the SECOND "Submit", then close the popover.

  // Match the Amazon popover
  const savedDialog = page.getByRole('dialog', { name: /Your changes have been saved/i });
  // Defensive selector(s) for the Done button in the popover footer
  const doneBtn = page
    .locator(
      '[data-test-id="modal-confirm-button"], .a-popover-footer [type="submit"], .a-popover-footer .a-button-text:has-text("Done")',
    )
    .first();

  const submitBtns = page.getByRole('button', { name: /^Submit$/ });

  // Try for up to ~30s total, checking for the saved dialog first each cycle.
  const deadline = Date.now() + 30_000;
  let clickedSubmit = false;

  while (Date.now() < deadline) {
    // 1) If the saved dialog is already visible, click Done and finish.
    if (await savedDialog.isVisible().catch(() => false)) {
      await clickWhenReady(page, doneBtn, 'Saved dialog: Done');
      await savedDialog.waitFor({ state: 'hidden', timeout: 10_000 }).catch(() => {});
      break;
    }

    // 2) Otherwise, if we haven't clicked Submit yet and there are 2+, click the SECOND one.
    if (!clickedSubmit && (await submitBtns.count()) > 1) {
      const secondSubmit = submitBtns.nth(1);
      if (await secondSubmit.isVisible().catch(() => false)) {
        await expect(secondSubmit).toBeEnabled();
        await secondSubmit.scrollIntoViewIfNeeded();
        await secondSubmit.click();
        clickedSubmit = true;
        // after clicking, loop back to wait for the saved dialog
        await page.waitForTimeout(300);
        continue;
      }
    }

    // 3) Short sleep before re-checking
    await page.waitForTimeout(200);
  }

  // Final safety: if the dialog popped after the loop, close it.
  if (await savedDialog.isVisible().catch(() => false)) {
    await clickWhenReady(page, doneBtn, 'Saved dialog: Done (post-loop)');
    await savedDialog.waitFor({ state: 'hidden', timeout: 10_000 }).catch(() => {});
  }

  // Click the "Source" button in the Description toolbar
  await clickWhenReady(page, page.getByRole('button', { name: 'Source' }), 'Description Source');

  // Wait 1s for the editor to switch
  await page.waitForTimeout(1000);

  // Paste the description HTML directly into the textarea
  const sourceBox = page.locator('textarea.cke_source');

  await fillWhenReady(
    page,
    sourceBox,
    `
  <p><b>ONE DATE. ONE BOOK. BIG FUN.</b></p>
   
  <p>Each title in the <b>What Happened On…</b> series spotlights a single calendar day—no filler—mixing bite-size facts, wild moments from history and nature, and puzzles that make learning feel like play. Every book has its own set of themed categories based on what happened on that date, so the vibe changes from title to title.</p>
   
  <p><b>What's inside</b></p>
  <ul>
      <li>Short, high-impact facts across day-specific themes (e.g., <i>History's Mic Drop Moments</i>, <i>Creature Feature</i>, <i>Big Brain Energy</i>, <i>The What Zone</i>)</li>
      <li>Bonus snippets: jokes, quotes, and follow-up questions</li>
      <li><b>Grid Gauntlet</b> crossword and <b>Letter Quest</b> word search</li>
      <li><b>Find TJ:</b> I am the author—hidden in the art. Can you spot me?</li>
  </ul>
   
  <p><b>Who it's for</b><br>
  <br>
  Perfect for ages 8–12 (independent reading or classrooms), with plenty for older readers too.</p>
   
  <p><b>Make it a challenge</b><br>
  <br>
  Pick birthdays or any date you like and compare with friends—whose day had the coolest discoveries, biggest breakthroughs, or wildest animal feats? Build a set of dates you care about most.</p>
  `,
  );

  // Wait 1s for the editor to switch
  await page.waitForTimeout(1000);

  // Click the "Source" button in the Description toolbar
  await clickWhenReady(page, page.getByRole('button', { name: 'Source' }), 'Description Source');

  // await expect(page.getByRole('heading', { level: 4, name: '2785' })).toBeVisible();

  await page.waitForTimeout(1000);
  // Open the Categories modal
  await expect(page.getByRole('button', { name: 'Choose categories' })).toBeVisible();
  await page.getByRole('button', { name: 'Choose categories' }).click();

  const categoriesModal = page.getByLabel('Categories');
  await expect(categoriesModal).toBeVisible();
  await expect(categoriesModal.getByText('Categories', { exact: true })).toBeVisible();

  /**
   * Clicks the *last* "Select one" dropdown (safer than hard-coded nths),
   * then walks the path of category labels, verifying each step.
   *
   * Examples:
   *  pickCategoryPath(["Children's Books", "History", "Exploration & Discovery"])
   *  pickCategoryPath(["Children's Books", "Science, Nature & How It Works", "Inventions & Inventors"])
   *  pickCategoryPath(["Children's Books", "Education & Reference", "Reference", "Almanacs"])
   */
  async function pickCategoryPath(path) {
    // helper: count visible "Select one" in the modal
    const selectOnes = () => categoriesModal.locator('span', { hasText: /^Select one$/ });

    for (let i = 0; i < path.length; i++) {
      const label = path[i];
      const isLeaf = i === path.length - 1;

      // 1) Open the newest dropdown for this depth
      const beforeCount = await selectOnes().count();
      const dropdown = selectOnes().last();

      await expect(dropdown).toBeVisible();
      await dropdown.scrollIntoViewIfNeeded();
      // trial click to flush overlay issues
      await dropdown.click({ trial: true }).catch(() => {});
      await dropdown.click();

      // 2) Choose the label inside the modal (scope to avoid hidden duplicates)
      // Try an option-like role first; fall back to exact text in the modal
      const optionByRole = categoriesModal.getByRole('option', { name: label }).first();
      const optionByText = categoriesModal.getByText(label, { exact: true }).first();

      const target = (await optionByRole.isVisible().catch(() => false))
        ? optionByRole
        : optionByText;

      await expect(target).toBeVisible();
      await target.scrollIntoViewIfNeeded();
      await target.click();

      if (isLeaf) {
        // 3) On leaf, tick the checkbox icon for that label
        const leafCheck = categoriesModal.locator('label', { hasText: label }).locator('i').first();
        await expect(leafCheck).toBeVisible();
        await leafCheck.click();

        // Optional: best-effort breadcrumb verify (scoped to modal)
        try {
          await expect(
            categoriesModal
              .locator('div')
              .filter({ hasText: new RegExp(`^${escapeRegExp(label)}$`) })
              .locator('span'),
          ).toBeVisible({ timeout: 5000 });
        } catch {}
      } else {
        // 4) After a non-leaf pick, wait for a NEW "Select one" to appear for the next level
        await expect.poll(async () => await selectOnes().count()).toBeGreaterThan(beforeCount);
        // brief settle
        await categoriesModal.page().waitForTimeout(100);
      }
    }
  }

  /** Adds another category row and waits for the row count to increase. */
  async function addAnotherCategoryRow() {
    const rowsBefore = await categoriesModal
      .locator('div:has-text("Books")')
      .count()
      .catch(() => 0);
    await expect(page.getByRole('button', { name: 'Add another category' })).toBeVisible();
    await page.getByRole('button', { name: 'Add another category' }).click();

    // Wait for a new "Select one" to appear (more robust than DOM nths)
    await expect
      .poll(async () => {
        return await categoriesModal.locator('span', { hasText: /^Select one$/ }).count();
      })
      .toBeGreaterThan(0);

    // Also try to ensure a new row appeared (best-effort; structure can vary)
    await expect
      .poll(async () => {
        return await categoriesModal
          .locator('div:has-text("Books")')
          .count()
          .catch(() => rowsBefore);
      })
      .toBeGreaterThan(rowsBefore);
  }

  // Small utility for safe regex construction
  function escapeRegExp(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  /* -------------------------
   Your three category picks
   ------------------------- */

  // 1) Children's Books > History > Exploration & Discovery
  await pickCategoryPath(["Children's Books", 'History', 'Exploration & Discovery']);

  // Add another category
  await addAnotherCategoryRow();

  // 2) Children's Books > Science, Nature & How It Works > Inventions & Inventors
  await pickCategoryPath([
    "Children's Books",
    'Science, Nature & How It Works',
    'Inventions & Inventors',
  ]);

  // Add another category
  await addAnotherCategoryRow();

  // 3) Children's Books > Education & Reference > Reference > Almanacs
  await pickCategoryPath(["Children's Books", 'Education & Reference', 'Reference', 'Almanacs']);

  // Save
  await expect(page.getByRole('button', { name: 'Save categories' })).toBeVisible();
  await page.getByRole('button', { name: 'Save categories' }).click();

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

  await waitVisible(page, 'role=link[name="Approve"]', 'Approve link visible');
  await clickWhenReady(page, page.getByRole('link', { name: 'Approve' }), 'Approve preview');

  // (Optional) publish…
  // await clickWhenReady(page, page.getByRole('button', { name: 'Publish Your Paperback Book' }), 'Publish');
});
