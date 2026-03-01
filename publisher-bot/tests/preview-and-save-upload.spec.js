// verify-existing-manuscript-live-filter.spec.js
// Opens KDP Bookshelf, filters to LIVE titles, opens Edit paperback content
// for each DOY from the DOYS env variable, handles the step-access popover
// if present, asserts the page title matches the expected date, and checks
// that "full_manuscript.pdf" is already uploaded (success banner visible).

const { test, expect } = require('@playwright/test');

// Collect manuscript checks across all DOYs so we can log a JSON summary at the end
const manuscriptCheckSummary = [];

// --- helper logging ----------------------------------------------------

function log(msg) {
  console.log(`[verify-manuscript] ${msg}`);
}

// --- helpers -----------------------------------------------------------

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

function doyToMonthDay(doy, year = 2024) {
  // Use leap year so DOY 366 works
  const date = new Date(Date.UTC(year, 0, 1));
  date.setUTCDate(doy);
  return { monthName: MONTHS[date.getUTCMonth()], day: date.getUTCDate() };
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

async function ensureVisible(locator) {
  try {
    await locator.scrollIntoViewIfNeeded();
  } catch {}
  await locator.waitFor({ state: 'visible', timeout: 0 });
}

async function setMarketplacePrice(page, marketCode, value) {
  const wrapper = page.locator(`#data-pricing-print-${marketCode}-price-input`);
  const input = wrapper.locator('input.price-input');

  await fillSimpleNoIdle(page, input, value, `Price ${marketCode.toUpperCase()}`);
}

async function fillSimpleNoIdle(page, locator, value, label = '') {
  const name = label || locator.toString();
  await waitReady(page, locator, name);
  log(`FILL (simple-no-idle) → ${name} = ${JSON.stringify(value).slice(0, 120)}`);
  await locator.fill(value);
  // tiny pause so React/KDP bindings fire, but no networkidle wait
  await page.waitForTimeout(300);
}

async function waitReady(page, locator, label = '') {
  const name = label || locator.toString();
  log(`WAIT ready → ${name}`);
  await locator.waitFor({ state: 'visible', timeout: 0 });
  await expect(locator).toBeEnabled({ timeout: 0 });
}

async function waitCalm(page) {
  log('WAIT network idle…');
  await page.waitForLoadState('networkidle', { timeout: 0 });
  await page.waitForTimeout(200);
  log('…network idle OK');
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

// --- main core: navigate and verify for a single DOY -------------------

async function runForDoyVerifyExistingManuscript(page, doy) {
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

  let usedFallbackMoreActions = false;

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
  let moreActionsButton = actionsCell.locator('button[aria-label="more actions"]').first();

  log('Waiting for "more actions" button (aria-label) to be visible for up to 5 seconds…');
  try {
    // Try primary selector first
    await moreActionsButton.waitFor({ state: 'visible', timeout: 5_000 });
  } catch (err) {
    // Fallback: older/alternate selector using the overflow-action-button class
    log(
      `"more actions" button with aria-label not visible within 5 seconds; ` +
        'trying fallback selector button.overflow-action-button…',
    );

    const fallback = actionsCell.locator('button.overflow-action-button').first();
    await fallback.waitFor({ state: 'visible', timeout: 5_000 });
    moreActionsButton = fallback;
    usedFallbackMoreActions = true;
  }

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

  let rawTitleOnContent = (await titleOnContentLocator.textContent()) ?? '';

  // --- step-access handling -------------------------------------------
  const stepAccessPopover = page.locator('#step-access-alert-popover');
  const stepAccessMessage = page.locator('#step-access-message');
  const stepAccessGoBackLink = page.locator('#step-access-redirect-link');

  log('Checking for step-access popover for up to 5 seconds...');

  try {
    await stepAccessPopover.waitFor({ state: 'visible', timeout: 5_000 });

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
      log('No step-access popover visible within 5 seconds; continuing normally.');
    } else {
      throw e;
    }
  }
  // --------------------------------------------------------------------

  const titleOnContent = rawTitleOnContent.replace(/\s+/g, ' ').trim();
  if (!titleOnContent) {
    throw new Error('Could not read title from #data-print-book-title-text on content page');
  }

  log(`Title found on content page: ${JSON.stringify(titleOnContent)}`);

  // Assert that the title on the Edit paperback content page matches the DOY we are running
  const expectedTitle = `${monthName} ${day}`; // e.g. "January 1", "March 29"
  expect(
    titleOnContent,
    `Content page title mismatch for DOY=${doy}. ` +
      `Expected "${expectedTitle}", got ${JSON.stringify(titleOnContent)}`,
  ).toBe(expectedTitle);

  // Now assert that the manuscript "full_manuscript.pdf" is already uploaded
  const manuscriptSuccess = page
    .locator('#data-print-book-publisher-interior-file-upload-success .success-header')
    .first();

  log('Waiting up to 5 seconds for manuscript success banner for full_manuscript.pdf...');

  let manuscriptOk = false;
  let bannerText = '';

  try {
    // Wait only 5 seconds for the success banner to show
    await manuscriptSuccess.waitFor({ state: 'visible', timeout: 5_000 });
    bannerText = ((await manuscriptSuccess.textContent()) ?? '').trim();

    if (bannerText.includes('full_manuscript.pdf')) {
      manuscriptOk = true;
      log('Confirmed manuscript "full_manuscript.pdf" is shown as uploaded.');
    } else {
      log(
        `Manuscript banner visible but does not contain expected filename. ` +
          `Got: ${JSON.stringify(bannerText)}`,
      );
    }
  } catch (err) {
    // Timed out or some other error
    log(`Manuscript success banner did not become visible within 5 seconds. ` + `Error: ${err}`);
    try {
      // Try to read any text anyway (might still exist in DOM)
      bannerText = ((await manuscriptSuccess.textContent()) ?? '').trim();
    } catch {
      bannerText = '';
    }
  }

  // Record result into shared JSON summary
  manuscriptCheckSummary.push({
    doy,
    expected: 'full_manuscript.pdf',
    okManuscript: manuscriptOk, // <- explicit "ok" flag
    bannerText,
    url: page.url(),
    usedFallbackMoreActions, // <- whether we used the fallback selector
  });

  // Still enforce the expectation so the test fails if it's not correct
  expect(
    manuscriptOk,
    `Expected manuscript success banner with "full_manuscript.pdf" for DOY=${doy}. ` +
      `Got bannerText=${JSON.stringify(bannerText)}`,
  ).toBe(true);

  // Click "Launch Previewer"
  await clickWhenReady(
    page,
    page.getByRole('button', { name: 'Launch Previewer' }),
    'Launch Previewer',
  );

  // Wait for and click "Approve"
  const approveLink = page.getByRole('link', { name: 'Approve' });
  await clickWhenReady(page, approveLink, 'Approve preview');

  await waitCalm(page); // let it navigate back to content and settle
  console.log('[Preview] Approved preview, back on Content page.');

  const confirmCheckbox = page.getByLabel(
    /By clicking this, I confirm that my answers are accurate/i,
  );
  const saveAndContinueButton = page.getByRole('button', { name: 'Save and Continue' });
  const publishBtn = page.getByRole('button', { name: 'Publish Your Paperback Book' });

  let reachedPricing = false;

  for (let attempt = 1; attempt <= 5; attempt++) {
    log(`Save & Continue attempt ${attempt}`);

    // 1) Click Save & Continue first
    log('Clicking Save & Continue...');
    await clickWhenReady(
      page,
      saveAndContinueButton,
      `Save & Continue (Content, attempt ${attempt})`,
    );

    try {
      // 2) Wait up to 3 seconds for the Publish button
      log(
        'Waiting up to 3 seconds for "Publish Your Paperback Book" button to confirm pricing page is loaded...',
      );
      await publishBtn.waitFor({ state: 'visible', timeout: 3_000 });
      await expect(publishBtn).toBeEnabled();

      log('"Publish Your Paperback Book" button is visible and enabled – reached pricing page.');
      reachedPricing = true;
      break;
    } catch (err) {
      // 3) Publish button still not visible – try the checkbox toggle fix
      log(
        `"Publish Your Paperback Book" button not visible after 3 seconds on attempt ${attempt}; applying checkbox toggle fix before retrying (if attempts remain).`,
      );

      try {
        log('Waiting up to 2 seconds for AI confirmation checkbox to be visible...');
        await confirmCheckbox.waitFor({ state: 'visible', timeout: 2_000 });

        log('AI confirmation checkbox visible; waiting 1s before unchecking...');
        await page.waitForTimeout(1_000);

        log('Unchecking AI confirmation checkbox via Playwright .uncheck()...');
        await confirmCheckbox.uncheck({ force: true, timeout: 2_000 });

        log('AI confirmation checkbox now unchecked; waiting 1s before re-checking...');
        await page.waitForTimeout(1_000);

        log('Re-checking AI confirmation checkbox via Playwright .check()...');
        await confirmCheckbox.check({ force: true, timeout: 2_000 });

        log('AI confirmation checkbox now checked; waiting 1s for KDP to register...');
        await page.waitForTimeout(1_000);

        // 4) Extra delay before we loop again
        log('Waiting 3 seconds before next Save & Continue attempt...');
        await page.waitForTimeout(3_000);

        // Let the page settle a bit more
        await waitCalm(page);
      } catch (checkboxErr) {
        // NEW: if checkbox flow fails, do one last Publish check and then give up
        log(
          `AI confirmation checkbox not visible or toggle failed (${checkboxErr}); ` +
            'doing one final check for "Publish Your Paperback Book" and then breaking out of the loop.',
        );

        try {
          await publishBtn.waitFor({ state: 'visible', timeout: 5_000 });
          await expect(publishBtn).toBeEnabled();
          log(
            '"Publish Your Paperback Book" button appeared after checkbox failure – treating as reached pricing page.',
          );
          reachedPricing = true;
        } catch {
          log(
            '"Publish Your Paperback Book" button still not visible after checkbox failure. ' +
              'Giving up further attempts for this DOY.',
          );
        }

        // Either way, stop looping – no more Save & Continue attempts.
        break;
      }
    }
  }

  expect(
    reachedPricing,
    'Expected to see "Publish Your Paperback Book" button after Save & Continue (up to 5 attempts).',
  ).toBe(true);

  // --- Paperback Rights & Pricing page ---
  console.log('[Pricing] Navigating to pricing page…');

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

  await clickWhenReady(page, publishBtn, 'Publish Your Paperback Book');

  // --- Wait for confirmation banner ---
  console.log('[Publish] Waiting for submission confirmation...');

  const submittedText = page
    .locator('span.a-text-bold', { hasText: 'Your paperback has been submitted' })
    .first(); // ← FORCE the first match

  await submittedText.waitFor({ state: 'visible', timeout: 60000 });

  console.log('[Publish] SUCCESS — Paperback has been submitted!');
  await page.waitForTimeout(5000);
}

// --- tests -------------------------------------------------------------

// One verification-only test per DOY from env
for (const doy of DOYS) {
  test(`verify existing manuscript only – DOY=${doy}`, async ({ page }, testInfo) => {
    // 10 minutes per DOY test (in ms)
    testInfo.setTimeout(5 * 60 * 1000);

    await runForDoyVerifyExistingManuscript(page, doy);
  });
}

test.afterAll(async () => {
  console.log('[verify-manuscript] Manuscript check summary (all DOYs):');
  console.log(JSON.stringify(manuscriptCheckSummary, null, 2));
});
