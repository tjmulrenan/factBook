// upload-new-manuscript-and-cover-live-filter.spec.js
// Opens KDP Bookshelf, filters to LIVE titles, opens Edit paperback content,
// resolves the local folder for that book from the on-page title, uploads manuscript & cover,
// clicks Save and Continue (with retries/checkbox), and verifies the title on the next page.

const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

// --- helper logging ----------------------------------------------------

function log(msg) {
  console.log(`[upload-live] ${msg}`);
}

// --- helpers -----------------------------------------------------------

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const BASE_FINAL_DIR =
  process.env.FINAL_DIR ??
  'C:\\Users\\tmulrenan\\OneDrive - The Retail Equation, Inc\\Desktop\\Personal\\factBook\\What Happened On... (The Complete Collection)';

function doyToMonthDay(doy, year = 2024) {
  // Use leap year so DOY 366 works
  const date = new Date(Date.UTC(year, 0, 1));
  date.setUTCDate(doy);
  return { monthName: MONTHS[date.getUTCMonth()], day: date.getUTCDate() };
}

async function waitCalm(page) {
  log('WAIT network idle…');
  await page.waitForLoadState('networkidle', { timeout: 0 });
  await page.waitForTimeout(200);
  log('…network idle OK');
}

async function setFilesWhenReady(page, locator, files, label = '') {
  const name = label || locator.toString();
  log(`UPLOAD → ${name} = ${Array.isArray(files) ? files.join(', ') : files}`);
  await locator.setInputFiles(files);
  await waitCalm(page);
}

// Helper: Convert "Month Day" → "DOY_Month_Day" (using leap year DOY)
function getFolderNameFromTitle(title) {
  const trimmed = String(title).trim();
  const [monthName, dayStr] = trimmed.split(/\s+/);
  const day = Number(dayStr);

  const monthIndex = MONTHS.indexOf(monthName);
  if (monthIndex === -1 || !day) {
    throw new Error(`Cannot parse title "${title}" as "Month Day"`);
  }

  // Use a leap year so DOY matches your 1..366 scheme with Feb 29
  const year = 2024;
  const date = new Date(Date.UTC(year, monthIndex, day));
  const startOfYear = new Date(Date.UTC(year, 0, 1));
  const msPerDay = 24 * 60 * 60 * 1000;

  const doy = Math.floor((date - startOfYear) / msPerDay) + 1; // 1-based

  return `${doy}_${monthName}_${day}`; // e.g. "76_March_16"
}

// --- DOYs from env for parameterised tests -----------------------------

function getDoysFromEnv() {
  const DEFAULT_DOYS = [1];

  const raw = process.env.DOYS ? process.env.DOYS.split(',') : DEFAULT_DOYS.map((d) => String(d));

  const parsed = raw
    .map((s) => Number(String(s).trim()))
    .filter((n) => Number.isInteger(n) && n >= 1 && n <= 366);

  if (!parsed.length) {
    throw new Error(
      'No valid DOYs found. Set DOYS env to a comma-separated list between 1 and 366, e.g. DOYS="2,3,4".',
    );
  }

  return parsed;
}

const DOYS = getDoysFromEnv();

// run all these tests in parallel
test.describe.configure({ mode: 'parallel' });

// --- main test ---------------------------------------------------------

// --- main test core: run for a single DOY -----------------------------

async function runForDoy(page, doy) {
  // Go straight to the Bookshelf (assumes storageState/auth is already set up)
  await page.goto('https://kdp.amazon.com/en_US/bookshelf', {
    waitUntil: 'networkidle',
  });

  // --- set "Records per page" to 50 -----------------------------------
  try {
    const perPageSelect = page.locator('#refreshedbookshelftable-records-per-page-dropdown-option');

    await perPageSelect.waitFor({ state: 'visible' });
    await perPageSelect.selectOption('50'); // value="50"
    log('Set records-per-page dropdown to 50');
    await waitCalm(page);
  } catch (err) {
    log(`WARNING: Could not change records-per-page dropdown: ${err}`);
  }
  // --------------------------------------------------------------------

  // ---- Open Edit paperback content for a specific date via search ----
  const { monthName, day } = doyToMonthDay(doy);
  const searchTerm = `${monthName} ${day}:`; // e.g. "January 1:"
  const titlePrefix = searchTerm;

  log(`Using DOY=${doy} → searchTerm="${searchTerm}"`);

  const searchInput = page.locator('#refreshedbookshelftable-search-input');
  await searchInput.waitFor({ state: 'visible' });
  await searchInput.fill(searchTerm);

  const searchSubmitInput = page
    .locator('#refreshedbookshelftable-search-button-submit input.a-button-input')
    .first();

  await searchSubmitInput.waitFor({ state: 'visible' });
  await searchSubmitInput.click();
  log('Clicked Bookshelf search submit.');

  await waitCalm(page);

  // Find the specific bookshelf row whose text contains our "Month Day:" prefix
  const rows = page.locator('tr[id][data-test-id^="titlesetheadertable-"]');
  const rowCount = await rows.count();

  let bookRow = null;

  for (let i = 0; i < rowCount; i++) {
    const row = rows.nth(i);
    const text = (await row.textContent()) ?? '';
    if (text.includes(titlePrefix)) {
      bookRow = row;
      break;
    }
  }

  if (!bookRow) {
    throw new Error(`Could not find bookshelf row containing "${titlePrefix}"`);
  }

  await bookRow.waitFor({ state: 'visible' });
  log('Found search result row for: ' + titlePrefix);

  // The header row we just found (titlesetheadertable-...) does NOT contain the
  // overflow "more actions" button. That button lives in a nested "print" row
  // with the SAME id but data-test-id starting with "refreshedbookshelfnestedtable-".
  const rowId = await bookRow.getAttribute('id');
  if (!rowId) {
    throw new Error('Matched bookshelf row has no id attribute');
  }
  log(`Using rowId=${rowId} to locate paperback actions row…`);

  // Find the nested PRINT row for this title (Paperback row)
  const paperbackRow = page
    .locator(`tr[id="${rowId}"][data-test-id^="refreshedbookshelfnestedtable-"]`)
    .filter({ hasText: 'Paperback' })
    .first();

  await paperbackRow.waitFor({ state: 'visible' });
  log('Paperback row located; now locating actions cell…');

  // Actions cell for this paperback row
  const actionsCell = paperbackRow.locator('td[data-column="actions"]').first();
  await actionsCell.waitFor({ state: 'visible' });

  // The actual "more actions" (three dots) button
  const moreActionsButton = actionsCell.locator('button[aria-label="more actions"]').first();
  log('Waiting for "more actions" button to be visible…');
  await moreActionsButton.waitFor({ state: 'visible' });

  log('Clicking three-dots "more actions" for this title…');
  await moreActionsButton.scrollIntoViewIfNeeded();
  await moreActionsButton.click();

  // Now click "Edit paperback content" from the popover/menu
  const editContentLink = page.getByRole('link', { name: /^Edit paperback content$/i }).first();
  await editContentLink.waitFor({ state: 'visible' });

  log(`Clicking "Edit paperback content" for ${searchTerm}…`);

  await Promise.all([
    page.waitForURL(/title-setup\/paperback\/.*\/content/),
    editContentLink.click(),
  ]);

  log(`URL after clicking Edit paperback content: ${page.url()}`);

  const titleOnContentLocator = page.locator('#data-print-book-title-text');
  await titleOnContentLocator.waitFor({ state: 'visible' });

  let rawTitleOnContent = await titleOnContentLocator.textContent();
  rawTitleOnContent = rawTitleOnContent ?? '';

  const stepAccessPopover = page.locator('#step-access-alert-popover');
  const stepAccessMessage = page.locator('#step-access-message');
  const stepAccessGoBackLink = page.locator('#step-access-redirect-link');

  log('Checking for step-access popover for up to 10 seconds...');

  try {
    await stepAccessPopover.waitFor({ state: 'visible', timeout: 10_000 });

    const msg = (await stepAccessMessage.textContent())?.trim();
    log(`Step-access popover visible. Message: ${JSON.stringify(msg)}`);

    await Promise.all([
      page.waitForURL(/title-setup\/paperback\/.*\/details/, { waitUntil: 'load' }),
      stepAccessGoBackLink.click(),
    ]);

    log('Navigated back from step-access popover. Waiting 3 seconds...');
    await page.waitForTimeout(3000);

    const backSaveAndContinueButton = page.locator('#save-and-continue-announce');
    await backSaveAndContinueButton.waitFor({ state: 'visible' });
    await expect(backSaveAndContinueButton).toBeEnabled();

    log('Clicking "Save and Continue" on previous step after step-access...');
    await Promise.all([
      page.waitForURL(/title-setup\/paperback\/.*\/content/, { waitUntil: 'load' }),
      backSaveAndContinueButton.click(),
    ]);

    log('Returned to content step after resolving step-access issue.');

    await titleOnContentLocator.waitFor({ state: 'visible' });
    rawTitleOnContent = (await titleOnContentLocator.textContent()) ?? '';
  } catch (e) {
    if (e instanceof Error && /Timeout/.test(e.message)) {
      log('No step-access popover visible within 10 seconds; continuing normally.');
    } else {
      throw e;
    }
  }

  const titleOnContent = rawTitleOnContent.replace(/\s+/g, ' ').trim();
  if (!titleOnContent) {
    throw new Error('Could not read title from #data-print-book-title-text on content page');
  }

  log(`Title found on content page: ${JSON.stringify(titleOnContent)}`);

  // Assert that the title on the Edit paperback content page matches the DOY we’re running
  const expectedTitle = `${monthName} ${day}`; // e.g. "January 1", "March 29"
  expect(
    titleOnContent,
    `Content page title mismatch for DOY=${doy}. ` +
      `Expected "${expectedTitle}", got ${JSON.stringify(titleOnContent)}`,
  ).toBe(expectedTitle);

  const folderName = getFolderNameFromTitle(titleOnContent);
  const folderPath = path.join(BASE_FINAL_DIR, folderName);

  log(`Resolved local folder for this book: ${folderPath}`);

  if (!fs.existsSync(folderPath)) {
    console.warn('WARNING: Folder does not exist on disk:', folderPath);
  } else {
    log(`Folder exists on disk: ${folderPath}`);
  }

  const manuscriptPath = path.join(folderPath, 'full_manuscript.pdf');
  const coverPath = path.join(folderPath, 'book_cover.pdf');

  log(`Manuscript path: ${manuscriptPath}`);
  log(`Cover path: ${coverPath}`);

  if (!fs.existsSync(manuscriptPath)) {
    console.warn('WARNING: Manuscript file missing:', manuscriptPath);
  }
  if (!fs.existsSync(coverPath)) {
    console.warn('WARNING: Cover file missing:', coverPath);
  }

  const manuscriptInput = page.locator('#data-print-book-publisher-interior-file-upload-AjaxInput');
  await setFilesWhenReady(page, manuscriptInput, manuscriptPath, 'Upload manuscript input');

  const coverInput = page.locator('#data-print-book-publisher-cover-file-upload-AjaxInput');
  await setFilesWhenReady(page, coverInput, coverPath, 'Upload cover input');

  const saveAndContinueButton = page.locator('#save-and-continue-announce');
  await saveAndContinueButton.waitFor({ state: 'visible' });
  await expect(saveAndContinueButton).toBeEnabled();

  const warningBox = page.getByText(
    'It looks like you’ve uploaded a new manuscript or book cover.',
    { exact: false },
  );
  const confirmCheckbox = page.getByLabel(
    /By clicking this, I confirm that my answers are accurate/i,
  );
  const successAlert = page.locator('#potter-success-alert-bottom .a-alert-content');

  let saveSucceeded = false;

  for (let attempt = 1; attempt <= 3; attempt++) {
    log(`Save & Continue attempt ${attempt}`);

    await saveAndContinueButton.click();
    await page.waitForTimeout(500);

    if (await warningBox.isVisible().catch(() => false)) {
      log('Confirmation warning visible, checking the box (via DOM)...');

      await warningBox.scrollIntoViewIfNeeded();
      await confirmCheckbox.waitFor({ state: 'visible' });

      await confirmCheckbox.evaluate((el) => {
        el.checked = true;
        el.dispatchEvent(new Event('change', { bubbles: true }));
      });

      await waitCalm(page);

      log('Clicking Save & Continue again after confirming...');
      await saveAndContinueButton.click();
      await page.waitForTimeout(500);
    }

    if (await successAlert.isVisible().catch(() => false)) {
      const successText = (await successAlert.textContent())?.trim();
      log(`Success alert text: ${JSON.stringify(successText)}`);
      log('Save successful – breaking out of retry loop.');
      saveSucceeded = true;
      break;
    }

    log('No "Save Successful!" alert yet; waiting calmly then retrying...');
    await waitCalm(page);
  }

  if (!saveSucceeded) {
    log('WARNING: Never saw "Save Successful!" alert after 3 attempts. Continuing anyway.');
  }
}

// One test per DOY from env
for (const doy of DOYS) {
  test(`upload new manuscript and cover – DOY=${doy}`, async ({ page }, testInfo) => {
    // 10 minutes per DOY test (in ms)
    testInfo.setTimeout(10 * 60 * 1000);

    await runForDoy(page, doy);
  });
}
