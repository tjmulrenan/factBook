// ---- constants ----
// You can override the folder in one run with:  $env:FINAL_DIR='C:\path\to\FINAL
const BASE_FINAL_DIR =
  process.env.FINAL_DIR ?? 'C:\\Personal\\What Happened On... (The Complete Collection)';

const SERIES_RESULT_ID = 'TEWDPW65QXM'; // only if you use the series step
const { test, expect } = require('@playwright/test');

const path = require('path');
const fs = require('fs');

// Allow multiple tests in this file to run in parallel
test.describe.configure({ mode: 'parallel' });

// List of DOYs to run if DOYS env var is not provided
const DEFAULT_DOYS = [16]; // change this default if you like

// Parse DOYS from env (e.g. DOYS=16,17,18,19) or fall back to DEFAULT_DOYS
const DOYS = (process.env.DOYS ? process.env.DOYS.split(',') : DEFAULT_DOYS)
  .map((s) => Number(String(s).trim()))
  .filter((n) => Number.isInteger(n) && n >= 1 && n <= 366);

if (DOYS.length === 0) {
  throw new Error('No valid DOYs supplied. Set DOYS env or update DEFAULT_DOYS.');
}

function norm(s) {
  return String(s ?? '')
    .replace(/[\u2018\u2019]/g, "'") // curly → straight apostrophe
    .replace(/\s+/g, ' ') // collapse spaces
    .trim()
    .toLowerCase();
}

async function fillWhenReadyNoIdle(page, locator, value, label = '') {
  const name = label || locator.toString();
  await waitReady(page, locator, name);
  log(`FILL (no-idle) → ${name} = ${JSON.stringify(value).slice(0, 120)}`);

  // Set value (CKEditor source textarea) and fire events so KDP saves it
  await locator.fill(''); // clear
  await locator.fill(value); // type
  await page.evaluate((el) => {
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }, await locator.elementHandle());

  // Give the UI a beat to register the change, not networkidle
  await page.waitForTimeout(400);

  // Verify it actually stuck (length check)
  await expect
    .poll(async () => (await locator.inputValue()).length, { timeout: 5000 })
    .toBeGreaterThan(50);
}

async function findBestOption(listbox, targetLabel) {
  const wanted = norm(targetLabel);
  // Cast a wide net for option-like elements
  const candidates = listbox.locator(
    [
      '[role="option"]',
      '[role="menuitem"]',
      'li',
      '.a-dropdown-item',
      '.a-dropdown-link',
      '[data-value]',
      'button',
      'span',
      'div',
    ].join(','),
  );

  const count = await candidates.count();
  let bestIdx = -1;
  let bestScore = -1;
  let bestText = '';

  for (let i = 0; i < count; i++) {
    const el = candidates.nth(i);
    const txt = norm(await el.innerText().catch(() => ''));
    if (!txt) continue;

    // simple scoring: exact → 3, startsWith → 2, includes → 1
    let score = -1;
    if (txt === wanted) score = 3;
    else if (txt.startsWith(wanted)) score = 2;
    else if (txt.includes(wanted)) score = 1;

    if (score > bestScore) {
      bestScore = score;
      bestIdx = i;
      bestText = txt;
      if (score === 3) break; // perfect
    }
  }

  if (bestIdx >= 0) {
    return { element: candidates.nth(bestIdx), matchedText: bestText };
  }
  return null;
}

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

// --------------------------------------------------
// Helpers
// --------------------------------------------------

// Set the description HTML using CKEditor directly (no Source click needed)
async function setDescriptionHtml(page, html) {
  log('[Description] Waiting for CKEditor instance…');

  // Wait until CKEditor is available and at least one instance exists
  await page.waitForFunction(() => {
    return (
      typeof window.CKEDITOR !== 'undefined' &&
      window.CKEDITOR.instances &&
      Object.keys(window.CKEDITOR.instances).length > 0
    );
  });

  await page.evaluate((html) => {
    // Grab the first CKEditor instance on the page
    const instances = window.CKEDITOR.instances;
    const firstKey = Object.keys(instances)[0];
    const editor = instances[firstKey];

    // Set the HTML and sync it back to the underlying textarea
    editor.setData(html);
    editor.updateElement();
  }, html);

  log('[Description] CKEditor data set successfully.');
}

async function openCoverUploadSection(page) {
  console.log('[Cover] Ensuring "Upload a cover you already have" section is open…');

  const accordionRoot = page.locator('#data-print-book-publisher-cover-choice-accordion');
  await expect(accordionRoot, 'Cover choice accordion not found').toBeVisible();

  const coverInput = page.locator('#data-print-book-publisher-cover-file-upload-AjaxInput');

  // This is the browse section inside the UPLOAD row
  const browseSection = accordionRoot
    .locator('[data-a-accordion-row-name="UPLOAD"] .file-upload-browse-section')
    .first();

  // 1) Short-circuit: if the browse section is already visible, we’re done.
  if (await browseSection.isVisible().catch(() => false)) {
    console.log('[Cover] Upload accordion already expanded (browse section visible).');
    return;
  }

  // 2) Locate the UPLOAD accordion row’s clickable link
  const uploadRowA11y = accordionRoot
    .locator('[data-a-accordion-row-name="UPLOAD"] .a-accordion-row-a11y')
    .first();

  const uploadRowLink = uploadRowA11y.locator('a.a-accordion-row').first();

  const maxAttempts = 1000;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    console.log(
      `[Cover] Attempt ${attempt}/${maxAttempts} to open "Upload a cover you already have" row…`,
    );

    // If it somehow became visible between attempts, bail out early
    if (await browseSection.isVisible().catch(() => false)) {
      console.log('[Cover] Upload accordion is now expanded (browse section visible).');
      return;
    }

    // Try to click the accordion row link
    await ensureVisible(uploadRowLink);
    await uploadRowLink.click({ force: true });

    // Give the UI a moment to toggle the accordion
    await page.waitForTimeout(800);

    // Check aria-expanded on the a11y wrapper
    const expanded = await uploadRowA11y.getAttribute('aria-expanded').catch(() => null);
    console.log(`[Cover] aria-expanded after click: ${expanded}`);

    // If aria-expanded is "true" and the browse section shows, we’re done
    if (expanded === 'true' && (await browseSection.isVisible().catch(() => false))) {
      console.log('[Cover] Upload accordion expanded; browse section visible.');
      return;
    }
  }

  // 3) Final debug: dump some text from the accordion and fail
  const snippet = (await accordionRoot.innerText().catch(() => '')).slice(0, 800);
  throw new Error(
    '[Cover] Failed to open "Upload a cover you already have" section after multiple attempts. ' +
      `Accordion text snippet: ${JSON.stringify(snippet)}`,
  );
}

async function setMarketplacePrice(page, marketCode, value) {
  const wrapper = page.locator(`#data-pricing-print-${marketCode}-price-input`);
  const input = wrapper.locator('input.price-input');

  await fillSimpleNoIdle(page, input, value, `Price ${marketCode.toUpperCase()}`);
}

async function selectSimpleDropdownByLabel(page, trigger, optionLabel, label = '') {
  const name = label || optionLabel;
  log(`[Details] Dropdown "${name}" – opening…`);

  await ensureVisible(trigger);
  await trigger.click({ force: true });

  const pop = page
    .locator('.a-popover[aria-hidden="false"]:visible .a-nostyle.a-list-link[role="listbox"]')
    .last();

  await expect(pop, `Dropdown list for "${name}" not visible`).toBeVisible();

  const option = pop
    .getByRole('option', { name: new RegExp(`^${escapeRegex(optionLabel)}$`, 'i') })
    .first();

  await expect(option, `Option "${optionLabel}" not visible in "${name}"`).toBeVisible();
  await option.click({ force: true });
  await page.waitForTimeout(200);
}

async function fillSimpleNoIdle(page, locator, value, label = '') {
  const name = label || locator.toString();
  await waitReady(page, locator, name);
  log(`FILL (simple-no-idle) → ${name} = ${JSON.stringify(value).slice(0, 120)}`);
  await locator.fill(value);
  // tiny pause so React/KDP bindings fire, but no networkidle wait
  await page.waitForTimeout(300);
}

// Add this helper near your other helpers
async function waitSelectedCategoryListed(categoriesModal, finalLabel, timeout = 12_000) {
  const rx = new RegExp(escapeRegex(finalLabel), 'i');

  // Summary text: "1 out of 3 category placements selected"
  const summary = categoriesModal
    .locator('span', { hasText: /out of 3 category placements selected/i })
    .first();
  await expect(summary, 'Selected-category summary not visible').toBeVisible({ timeout });

  // Anchor in the selected list that contains our label
  const anchor = categoriesModal
    .locator('ul.a-unordered-list.a-vertical, ul.a-unordered-list.a-nostyle.a-vertical')
    .locator('a.a-link-normal')
    .filter({ hasText: rx })
    .first();

  await expect(anchor, `Selected-category link for "${finalLabel}"`).toBeVisible({ timeout });

  const txt = await anchor.innerText();
  console.log(`[Categories] Selected list shows link: ${JSON.stringify(txt)}.`);
}

function escapeRegex(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// NEW: robust checkbox checker for leaf nodes
async function checkLeafCheckbox(categoriesModal, label) {
  const rx = new RegExp(`^\\s*${escapeRegex(label)}\\s*$`, 'i');

  // 1) Find the visible label span with the text (your sample class)
  const labelSpan = categoriesModal
    .locator('.a-label.a-checkbox-label:visible')
    .filter({ hasText: rx })
    .first();

  if (await labelSpan.isVisible().catch(() => false)) {
    // try to find a checkbox input in the same row/label
    const container = labelSpan
      .locator('xpath=ancestor-or-self::label | xpath=ancestor::*[contains(@class, "a-checkbox")]')
      .first();

    const input = container.locator('input[type="checkbox"]:visible').first();
    if (await input.isVisible().catch(() => false)) {
      await input.check({ force: true });
      await expect(input).toBeChecked();
      console.log(`[Categories] Checkbox ticked for "${label}".`);
      return true;
    }
  }

  // 2) Fallback: ARIA role by name (if KDP exposes it)
  const roleBox = categoriesModal
    .getByRole('checkbox', { name: new RegExp(escapeRegex(label), 'i') })
    .first();
  if (await roleBox.isVisible().catch(() => false)) {
    await roleBox.check({ force: true });
    await expect(roleBox).toBeChecked();
    console.log(`[Categories] Checkbox (role) ticked for "${label}".`);
    return true;
  }

  return false;
}

async function pickCategoryPath(page, categoriesModal, pathLabels, maxRetries = 5) {
  if (!Array.isArray(pathLabels) || pathLabels.length === 0) {
    throw new Error('pickCategoryPath: pathLabels must be a non-empty array');
  }
  console.time('[Categories] pickCategoryPath: ' + pathLabels.join(' > '));
  console.log('[Categories] Starting path:', JSON.stringify(pathLabels));

  const getPrompts = () =>
    categoriesModal.locator(
      '.a-dropdown-prompt:visible, [data-action="a-dropdown-button"] .a-button-text:visible',
    );

  const getVisiblePopover = () =>
    page
      .locator(
        '.a-popover[aria-hidden="false"]:visible, ' +
          '[role="listbox"]:visible, ' +
          '.a-popover-wrapper:has(.a-dropdown-link):visible',
      )
      .last();

  async function openLastDropdown() {
    const prompts = getPrompts();
    const count = await prompts.count();
    if (count === 0) throw new Error('No visible dropdown prompts found.');

    const idx = count - 1;
    const prompt = prompts.nth(idx);
    const trigger = prompt
      .locator('xpath=ancestor-or-self::*[@data-action="a-dropdown-button"]')
      .first();

    await expect(trigger, 'Dropdown trigger not visible').toBeVisible();
    await trigger.scrollIntoViewIfNeeded();
    await page.keyboard.press('Escape').catch(() => {}); // clear strays
    await trigger.click({ force: true });
    return { idx, prompt, trigger };
  }

  async function selectFromPopoverByLabel(label) {
    const pop = getVisiblePopover();
    await expect(pop, 'Popover/Listbox did not appear').toBeVisible();

    const options = pop.locator('.a-dropdown-link');
    const n = await options.count();
    if (n === 0) throw new Error('No options found in the opened popover.');

    const wanted = norm(label);
    let match = null;

    for (let i = 0; i < n; i++) {
      const opt = options.nth(i);
      const txt = norm(await opt.innerText().catch(() => ''));
      if (txt === wanted) {
        match = opt;
        break;
      }
    }
    if (!match) {
      for (let i = 0; i < n; i++) {
        const opt = options.nth(i);
        const txt = norm(await opt.innerText().catch(() => ''));
        if (txt.includes(wanted)) {
          match = opt;
          break;
        }
      }
    }
    if (!match) {
      const dump = norm(await pop.innerText().catch(() => ''));
      console.log(
        '[Categories] Could not find option; listbox text (trimmed):',
        dump.slice(0, 600),
      );
      throw new Error(`Option not found for "${label}" (apostrophes/spacing may differ)`);
    }

    await match.scrollIntoViewIfNeeded();
    await match.click({ force: true });
  }

  async function waitForChipText(idx, expectedText, timeout = 8000) {
    const prompts = getPrompts();
    await expect
      .poll(
        async () => {
          const countNow = await prompts.count();
          if (idx >= countNow) return '';
          return norm(
            await prompts
              .nth(idx)
              .innerText()
              .catch(() => ''),
          );
        },
        { timeout },
      )
      .toContain(norm(expectedText));
  }

  for (let i = 0; i < pathLabels.length; i++) {
    const label = pathLabels[i];
    const isLeaf = i === pathLabels.length - 1;

    let success = false;
    let lastError = null;

    for (let attempt = 1; attempt <= maxRetries && !success; attempt++) {
      try {
        console.log(
          `[Categories] Step ${i + 1}/${
            pathLabels.length
          } → "${label}" (attempt ${attempt}/${maxRetries})`,
        );

        // **Leaf-first checkbox path**: if this is the last segment, try to tick a checkbox directly.
        if (isLeaf) {
          const ticked = await checkLeafCheckbox(categoriesModal, label);
          if (ticked) {
            await page.waitForTimeout(150);
            await waitSelectedCategoryListed(categoriesModal, label);
            success = true;
            break;
          }
          // If no checkbox, fall through to dropdown selection (some leaves are still in a popover).
        }

        const beforeCount = await getPrompts().count();

        // Try dropdown → label selection
        const { idx } = await openLastDropdown();
        await selectFromPopoverByLabel(label);
        await waitForChipText(idx, label);
        console.log(`[Categories] Selected "${label}" and chip updated.`);

        if (isLeaf) {
          // Optionally tick if a checkbox also appears
          const ticked = await checkLeafCheckbox(categoriesModal, label);
          // In either case, wait for the selected list to reflect it
          await waitSelectedCategoryListed(categoriesModal, label); // <-- add this
          success = true;
        } else {
          // Non-leaf: either a new column appears OR (in some flows) a checkbox list appears instead.
          const deadline = Date.now() + 15000;
          while (Date.now() < deadline) {
            const promptsNow = await getPrompts().count();
            if (promptsNow === beforeCount + 1) {
              // New column case
              await expect
                .poll(
                  async () => {
                    const txt = await getPrompts()
                      .nth(promptsNow - 1)
                      .innerText()
                      .catch(() => '');
                    return norm(txt);
                  },
                  { timeout: 8000 },
                )
                .toContain(norm('Select one'));
              console.log('[Categories] Next-level dropdown ready.');
              break;
            }
            // Alt case: checkbox list for next step showed up early (rare on non-leaf, but be defensive)
            const nextLabel = pathLabels[i + 1];
            if (nextLabel) {
              const hasNextAsCheckbox = await categoriesModal
                .locator('.a-label.a-checkbox-label:visible')
                .filter({ hasText: new RegExp(escapeRegex(nextLabel), 'i') })
                .first()
                .isVisible()
                .catch(() => false);
              if (hasNextAsCheckbox) {
                console.log(
                  '[Categories] Detected checkbox list for next step instead of a column.',
                );
                break;
              }
            }
            await page.waitForTimeout(150);
          }
          success = true;
        }
      } catch (err) {
        lastError = err;
        console.warn(`[Categories] Attempt ${attempt} failed for "${label}":`, err?.message || err);
        await page.keyboard.press('Escape').catch(() => {});
        await page.waitForTimeout(250);
        if (attempt === maxRetries) throw err;
      }
    }

    if (!success && lastError) throw lastError;
  }

  console.timeEnd('[Categories] pickCategoryPath: ' + pathLabels.join(' > '));
}

/** Adds another category row and waits for the row count to increase. */
/** Adds another category row and waits for the number of dropdowns to increase. */
async function addAnotherCategoryRow(page, categoriesModal) {
  console.log('[Categories] Adding another category row…');

  // Each row has a <span class="a-dropdown-container"><select class="a-native-dropdown">…</select>
  const dropdowns = () => categoriesModal.locator('.a-dropdown-container select.a-native-dropdown');

  const before = await dropdowns()
    .count()
    .catch(() => 0);
  console.log(`[Categories] Dropdowns before add: ${before}`);

  const addBtn = categoriesModal.getByRole('button', { name: /Add another category/i });
  await expect(addBtn).toBeVisible();
  await addBtn.click();

  console.log('[Categories] Waiting for dropdown count to increase…');
  await expect
    .poll(async () => {
      const c = await dropdowns().count();
      console.log(`[Categories] Current dropdown count: ${c}`);
      return c;
    })
    .toBeGreaterThan(before);

  console.log('[Categories] New category row added.');
}

// ---------------- TEST ----------------
for (const doy of DOYS) {
  test(`publish paperback from DOY ${doy}`, async ({ page }) => {
    page.setDefaultTimeout(0);
    page.setDefaultNavigationTimeout(0);

    // optional: log browser events
    page.on('console', (msg) => {
      const type = msg.type();
      const text = msg.text();

      // Ignore CSP + batch telemetry noise from Amazon
      if (text.includes('Content Security Policy directive') || text.includes('/1/batch/2/OE/')) {
        return;
      }

      log(`BROWSER [${type}]`, text);
    });
    page.on('request', (req) => log('REQUEST →', req.method(), req.url()));
    page.on('response', (res) => log('RESPONSE ←', res.status(), res.url()));

    // ---- read DOY and derive title/paths/keywords ----
    const doyNum = doy; // value from DOYS array
    const doyRaw = String(doyNum);
    log(`DOY: ${doyNum} (source: DOYS array)`);

    if (!Number.isInteger(doyNum) || doyNum < 1 || doyNum > 366) {
      throw new Error(`Bad DOY: ${doyRaw}`);
    }

    const { monthName, day } = doyToMonthDay(doyNum);

    const title = `${monthName} ${day}`;
    const sign = zodiac(monthName, day);
    const keywords0 = buildKeywords(monthName, day, sign);

    const folder = `${doyNum}_${monthName}_${day}`;
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

    // UNCOMMENT BELOW
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
    // UNCOMMENT ABOVE

    console.time('Description: set via CKEditor');
    console.log('[Description] Setting description HTML via CKEditor…');

    const descriptionHtml = `<p><b></b></p>

<p>Each title in the <b>What Happened On…</b> series spotlights a single calendar day—no filler—mixing bite-size facts, wild moments from history and nature, and puzzles that make learning feel like play. Every book has its own set of themed categories based on what happened on that date, so the vibe changes from title to title.</p>

<p><b>What's inside</b></p>
<ul>
  <li>Short, high-impact facts across day-specific themes (e.g., <i>History's Mic Drop Moments</i>, <i>Creature Feature</i>, <i>Big Brain Energy</i>, <i>The What Zone</i>)</li>
  <li>Bonus snippets: jokes, quotes, and follow-up questions</li>
  <li><b>Grid Gauntlet</b> crossword and <b>Letter Quest</b> word search</li>
  <li><b>Find TJ:</b> I am the author—hidden in the art. Can you spot me?</li>
</ul>

<p><b>Who it's for</b><br>
</p>

<p><b></b><br>
</p>`;

    await setDescriptionHtml(page, descriptionHtml);

    console.timeEnd('Description: set via CKEditor');

    // small settle pause
    await page.waitForTimeout(2000);

    // await clickWhenReady(page, page.getByRole('button', { name: 'Source' }), 'Description Source');

    console.log('[Details] Waiting for remaining-character counter to update from 4000…');

    // Find the wrapper that contains the remaining-character UI
    const remainingWrapper = page
      .locator('div')
      .filter({ hasText: /remaining characters/i })
      .last();
    const remainingCounter = remainingWrapper.locator('h4').first();

    await expect(remainingWrapper).toBeVisible();
    await expect(remainingCounter).toBeVisible();

    let remaining = NaN;

    // Retry for up to ~20s (40 × 500ms) until it changes from 4000
    for (let attempt = 1; attempt <= 40; attempt++) {
      const raw = (await remainingCounter.innerText().catch(() => '')).trim();
      const numeric = raw.replace(/[^\d]/g, '');
      remaining = Number(numeric || NaN);

      console.log(
        `[Details] Remaining counter attempt ${attempt}: raw=${JSON.stringify(raw)} → ${remaining}`,
      );

      // Stop once it’s a real value and not the initial 4000
      if (Number.isFinite(remaining) && remaining !== 4000) {
        break;
      }

      await page.waitForTimeout(500);
    }

    // If it never changed, dump some HTML to help debug
    if (!Number.isFinite(remaining) || remaining === 4000) {
      const htmlSnippet = (await remainingWrapper.innerHTML().catch(() => '')).slice(0, 500);
      throw new Error(
        `[Details] Remaining-character counter never updated from 4000. ` +
          `HTML snippet: ${JSON.stringify(htmlSnippet)}`,
      );
    }

    // Instead of hard-coding 2797, just assert it looks sane.
    // If you *really* want 2797, swap this block back to a strict equality check.
    if (!(remaining > 2000 && remaining < 4000)) {
      throw new Error(
        `[Details] Remaining-character counter was ${remaining}, expected between 2001 and 3999. ` +
          `If you changed the description text, update this assertion.`,
      );
    }

    console.log(`[Details] Remaining-character counter looks good: ${remaining}.`);

    // ------------------------------------------------------------
    // Fill edition + author + age ranges BEFORE opening categories
    // ------------------------------------------------------------

    console.log('[Details] Filling edition number, author, and age ranges…');

    // Edition number = 1
    await fillSimpleNoIdle(
      page,
      page.locator('#data-print-book-edition-number'),
      '1',
      'edition number',
    );

    // Primary author: TJ Mulrenan
    await fillSimpleNoIdle(
      page,
      page.locator('#data-print-book-primary-author-first-name'),
      'TJ',
      'author first name',
    );
    await fillSimpleNoIdle(
      page,
      page.locator('#data-print-book-primary-author-last-name'),
      'Mulrenan',
      'author last name',
    );

    // Reading age range: 8 – 18+
    const minAgeSelect = page.locator('#data-print-book-reading-interest-age-start-input-native');
    const maxAgeSelect = page.locator('#data-print-book-reading-interest-age-end-input-native');

    log('[Details] Setting age range 8–18+…');

    await waitReady(page, minAgeSelect, 'Age minimum select');
    await waitReady(page, maxAgeSelect, 'Age maximum select');

    // select by visible label
    await minAgeSelect.selectOption({ label: '8' });
    await maxAgeSelect.selectOption({ label: '18+' });

    // small pause so KDP bindings fire
    await page.waitForTimeout(300);

    // optional sanity checks
    await expect(minAgeSelect).toHaveValue('8');
    await expect(maxAgeSelect).toHaveValue('18');

    console.log('[Details] Edition, author, and age ranges filled.');

    console.log('[Categories] Opening categories modal…');
    await page.waitForTimeout(1000);
    // Open the Categories modal
    const chooseBtn = page.getByRole('button', { name: /Choose categories/i });
    await expect(chooseBtn).toBeVisible();
    await chooseBtn.click();

    const categoriesModal = page.getByRole('dialog', { name: /Categories/i });
    await expect(categoriesModal.getByText(/^Categories$/)).toBeVisible();
    await expect(categoriesModal).toBeVisible();
    await expect(categoriesModal.getByText('Categories', { exact: true })).toBeVisible();
    console.log('[Categories] Modal visible.');

    /* -------------------------
   Your three category picks
   ------------------------- */

    console.log('[Categories] Pick #1 — Children’s Books > History > Exploration & Discovery');
    await pickCategoryPath(page, categoriesModal, [
      "Children's Books",
      'History',
      'Exploration & Discovery',
    ]);

    console.log('[Categories] Adding row between pick #1 and #2…');
    await addAnotherCategoryRow(page, categoriesModal);

    console.log(
      '[Categories] Pick #2 — Children’s Books > Science, Nature & How It Works > Inventions & Inventors',
    );
    await pickCategoryPath(page, categoriesModal, [
      "Children's Books",
      'Science, Nature & How It Works',
      'Inventions & Inventors',
    ]);

    console.log('[Categories] Adding row between pick #2 and #3…');
    await addAnotherCategoryRow(page, categoriesModal);

    console.log(
      '[Categories] Pick #3 — Children’s Books > Education & Reference > Reference > Almanacs',
    );
    await pickCategoryPath(page, categoriesModal, [
      "Children's Books",
      'Education & Reference',
      'Reference',
      'Almanacs',
    ]);

    console.log('[Categories] Saving categories…');
    const saveCatsBtn = page.getByRole('button', { name: /Save categories/i });
    await expect(saveCatsBtn).toBeVisible();
    await saveCatsBtn.click();

    console.time('Details: Save & Continue');
    console.log('[Details] Clicking "Save and Continue"…');
    // Continue to Content
    await clickWhenReady(
      page,
      page.getByRole('button', { name: 'Save and Continue' }),
      'Save & Continue (Details)',
    );
    console.timeEnd('Details: Save & Continue');
    console.log('[Details] Completed.');

    // Content choices (2nd page)

    // First click the Assign ISBN button
    await clickWhenReady(page, page.getByRole('button', { name: /^Assign ISBN$/ }), 'Assign ISBN');

    // Now wait for the popover to appear
    const isbnPopover = page.getByRole('dialog', { name: /Free KDP ISBN/i });
    await expect(isbnPopover).toBeVisible({ timeout: 10000 });

    // Confirm inside the popover
    const confirmISBN = isbnPopover.locator('#free-isbn-confirm-button');
    await clickWhenReady(page, confirmISBN, 'Confirm ISBN');

    // Small wait for it to process + close
    await page.waitForTimeout(800);

    await clickWhenReady(
      page,
      page.getByRole('button', { name: 'Standard color interior with' }),
      'Interior: Standard color',
    );
    await clickWhenReady(page, page.getByRole('button', { name: 'Bleed (PDF only)' }), 'Bleed: On');
    await clickWhenReady(
      page,
      page.getByRole('button', { name: 'Glossy' }),
      'Cover finish: Glossy',
    );

    // ---- Manuscript upload (no button click) ----
    const manuscriptInput = page.locator(
      '#data-print-book-publisher-interior-file-upload-AjaxInput',
    );

    await setFilesWhenReady(page, manuscriptInput, manuscriptPath, 'Upload manuscript input');
    await waitCalm(page);

    // await page.goto('https://kdp.amazon.com/en_US/title-setup/paperback/GXAE62B914F/content', {
    //   waitUntil: 'networkidle',
    // });
    // await waitCalm(page);

    // ---- Cover upload (robust accordion handling) ----
    console.log('[Cover] Opening "Upload a cover you already have" section…');
    await openCoverUploadSection(page);

    // Now the upload widget should be visible
    const coverInput = page.locator('#data-print-book-publisher-cover-file-upload-AjaxInput');
    await setFilesWhenReady(page, coverInput, coverPath, 'Upload cover input');
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

    // Specifically pick the "None" option for *Translations* only
    const translationsNoneOption = page.locator(
      'li[aria-labelledby="generative-ai-questionnaire-translations_0"]',
    );
    await clickWhenReady(page, translationsNoneOption, 'AI Translations: None');

    // --- Save & Preview / Approve (ALWAYS run through previewer) ---
    console.log('[Content] Clicking "Save and Continue"…');
    await clickWhenReady(
      page,
      page.getByRole('button', { name: 'Save and Continue' }),
      'Save & Continue (Content)',
    );

    // Wait for the "Please preview and approve your book" error banner
    console.log('[Preview] Waiting for "Please preview and approve your book" banner…');
    const previewError = page
      .locator('#potter-error-alert-bottom .a-alert-content')
      .filter({ hasText: /Please preview and approve your book/i });

    await previewError.waitFor({ state: 'visible', timeout: 30_000 });
    console.log('[Preview] Banner visible, launching Previewer…');

    // Click "Launch Previewer"
    await clickWhenReady(
      page,
      page.getByRole('button', { name: 'Launch Previewer' }),
      'Launch Previewer',
    );

    // Wait for and click "Approve"
    const approveLink = page.getByRole('link', { name: 'Approve' });
    await clickWhenReady(page, approveLink, 'Approve preview');

    console.log('[Preview] Approved preview, back on Content page.');

    // Now Save & Continue again – this time it should succeed
    await clickWhenReady(
      page,
      page.getByRole('button', { name: 'Save and Continue' }),
      'Save & Continue (Content, after preview)',
    );

    // --- Paperback Rights & Pricing page ---
    console.log('[Pricing] Navigating to pricing page…');

    // await page.goto('https://kdp.amazon.com/en_US/title-setup/paperback/E7DJ1FZANK8/pricing', {
    //   waitUntil: 'networkidle',
    // });
    // await waitCalm(page);

    // Assert we’re really on the pricing page by waiting for US price input
    const usPriceInput = page
      .locator('#data-pricing-print-us-price-input')
      .locator('input.price-input');

    await waitReady(page, usPriceInput, 'US price input');
    console.log('[Pricing] Pricing grid visible, filling prices…');

    // US – $9.99
    await setMarketplacePrice(page, 'us', '9.99');

    // UK – £7.99
    await setMarketplacePrice(page, 'uk', '7.99');

    // DE / FR / ES / IT / NL / BE / IE – €9.99
    await setMarketplacePrice(page, 'de', '9.99');
    await setMarketplacePrice(page, 'fr', '9.99');
    await setMarketplacePrice(page, 'es', '9.99');
    await setMarketplacePrice(page, 'it', '9.99');
    await setMarketplacePrice(page, 'nl', '9.99');
    await setMarketplacePrice(page, 'be', '9.99');
    await setMarketplacePrice(page, 'ie', '9.99');

    // PL – 40 zł
    await setMarketplacePrice(page, 'pl', '40');

    // SE – 110 kr
    await setMarketplacePrice(page, 'se', '110');

    // JP – ¥1478
    await setMarketplacePrice(page, 'jp', '1478');

    // CA – $13.99
    await setMarketplacePrice(page, 'ca', '13.99');

    // AU – $15.26
    await setMarketplacePrice(page, 'au', '15.26');

    console.log('[Pricing] All marketplaces filled, publishing...');

    // --- Click Publish ---
    const publishBtn = page.getByRole('button', { name: 'Publish Your Paperback Book' });

    await clickWhenReady(page, publishBtn, 'Publish Your Paperback Book');

    // --- Wait for confirmation banner ---
    console.log('[Publish] Waiting for submission confirmation...');

    const submittedText = page
      .locator('span.a-text-bold', { hasText: 'Your paperback has been submitted' })
      .first(); // ← FORCE the first match

    await submittedText.waitFor({ state: 'visible', timeout: 60000 });

    console.log('[Publish] SUCCESS — Paperback has been submitted!');
    await page.waitForTimeout(5000);

    // (Optional) publish…
    // await clickWhenReady(page, page.getByRole('button', { name: 'Publish Your Paperback Book' }), 'Publish');
  });
}
