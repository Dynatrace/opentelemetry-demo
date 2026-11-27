import { Logger } from "winston";
import { Page } from "puppeteer";
import { IPageActions, PageActions, delay } from "@demoability/loadgen-core";
import { ACTION_DURATION_MS, PAGE_WAIT_UNTIL, Person } from "./config";
import { selectors } from "./selectors";

// ---------------------------------------------------------------------------
// Page-level waits
// These still need the raw Page because waitForFunction is not part of
// IPageActions — everything else goes through IPageActions + selectors.
// ---------------------------------------------------------------------------

export async function waitForBanner(
  page: Page,
  timeoutMs: number = 15_000,
): Promise<void> {
  try {
    await page.waitForFunction(
      () => {
        const img = document.querySelector<HTMLImageElement>(
          '[data-cy="banner-img"], img[src*="/images/Banner.png"]',
        );
        return img !== null && img.naturalWidth > 0;
      },
      { timeout: timeoutMs },
    );
  } catch {
    // swallow — banner may not be present on all deployments
  }
}

export async function waitForProductCard(
  page: Page,
  timeoutMs: number = 15_000,
): Promise<void> {
  try {
    await page.waitForFunction(
      () => {
        const els = document.querySelectorAll('[data-cy="product-card"]');
        return Array.from(els).some((el) => {
          const candidates = [el, ...Array.from(el.querySelectorAll("*"))];
          return candidates.some((candidate) => {
            const bg = getComputedStyle(candidate).backgroundImage;
            return bg && bg !== "none" && bg !== "";
          });
        });
      },
      { timeout: timeoutMs },
    );
  } catch {
    // swallow
  }
}

// ---------------------------------------------------------------------------
// Flow actions
// ---------------------------------------------------------------------------

export async function orderProduct(
  pageActions: IPageActions,
  logger: Logger,
): Promise<void> {
  const page = (pageActions as PageActions).page;

  await waitForProductCard(page);

  // getAllHandles does not wait — we rely on waitForProductCard having run first.
  const cards = await pageActions.getAllHandles(selectors.productCard);
  if (cards.length === 0) {
    const url = page.url();
    let errorText: string | undefined;
    try {
      const el = await page.$('[role="alert"], .error, [data-cy="error"]');
      if (el !== null && (await el.isIntersectingViewport())) {
        errorText = await el.evaluate((e) => (e as HTMLElement).innerText);
      }
    } catch {
      // ignore
    }
    logger.warn(
      `No product cards found on ${url}${errorText ? `: ${errorText}` : ""} — rescheduling`,
    );
    throw new Error("no product cards — reschedule");
  }

  const card = cards[Math.floor(Math.random() * cards.length)];

  // ProductCard renders as a <div> (non-focusable). loadgen-core's
  // scrollIntoView calls focus() then polls isIntersectingViewport(), but
  // focus() is a no-op on a plain div, so the poll would wait forever.
  // Scroll via the native JS API first so the div is already in the viewport
  // when navigateHandle's internal scrollIntoView check runs.
  await card
    .getHandle()
    .evaluate((el) => el.scrollIntoView({ block: "center" }));
  await delay(1_000);

  // navigateHandle: scrollIntoView (now a no-op: already in viewport) + click + waitForNavigation
  await pageActions.navigateHandle(card);
  await delay(2_000);

  const qty = [1, 2, 3, 4, 5, 10][Math.floor(Math.random() * 6)];
  await pageActions.selectOption(selectors.productQuantity, String(qty));
  await delay(1_000);

  // navigate: waitForSelector(visible) + scrollIntoView + click + waitForNavigation
  await pageActions.navigate(selectors.addToCart);
}

export async function completeCheckout(
  pageActions: IPageActions,
  person: Person,
  logger: Logger,
): Promise<void> {
  const page = (pageActions as PageActions).page;

  await pageActions.selectOption(selectors.currencySelect, person.userCurrency);
  await delay(ACTION_DURATION_MS);

  await pageActions.input(selectors.emailInput, person.email);
  await delay(ACTION_DURATION_MS);

  await pageActions.input(
    selectors.streetAddress,
    person.address.streetAddress,
  );
  await delay(ACTION_DURATION_MS);

  await pageActions.input(selectors.zipCode, String(person.address.zipCode));
  await delay(ACTION_DURATION_MS);

  await pageActions.input(selectors.city, person.address.city);
  await delay(ACTION_DURATION_MS);

  await pageActions.input(selectors.state, person.address.state);
  await delay(ACTION_DURATION_MS);

  await pageActions.input(selectors.country, person.address.country);
  await delay(ACTION_DURATION_MS);

  await fillCreditCardNumber(
    pageActions,
    String(person.creditCard.creditCardNumber),
  );
  await delay(ACTION_DURATION_MS);

  await pageActions.selectOption(
    selectors.expirationMonth,
    String(person.creditCard.creditCardExpirationMonth),
  );
  await delay(ACTION_DURATION_MS);

  await pageActions.selectOption(
    selectors.expirationYear,
    String(person.creditCard.creditCardExpirationYear),
  );
  await delay(ACTION_DURATION_MS);

  await pageActions.input(
    selectors.creditCardCvv,
    String(person.creditCard.creditCardCvv),
  );
  await delay(ACTION_DURATION_MS);

  try {
    // navigate: waitForSelector(visible) + click + waitForNavigation (load)
    await pageActions.navigate(selectors.placeOrder);
  } catch (e) {
    // Navigation did not complete — inspect the page for a visible reason.
    let reason: string | undefined;
    try {
      const invalid = await page.evaluate(() => {
        const els = [
          ...document.querySelectorAll<HTMLInputElement>(
            "input:invalid, select:invalid, textarea:invalid",
          ),
        ];
        if (els.length === 0) return null;
        return els
          .map((el) => {
            const id =
              el.id || el.name || el.placeholder || el.tagName.toLowerCase();
            return `${id}: ${el.validationMessage || "(no message)"}`;
          })
          .join("; ");
      });
      if (invalid) {
        reason = `form validation error — ${invalid}`;
      } else {
        const el = await page.$('[role="alert"], .error, [data-cy="error"]');
        if (el !== null && (await el.isIntersectingViewport())) {
          reason = `page error — ${await el.evaluate((e) => (e as HTMLElement).innerText)}`;
        }
      }
    } catch {
      // ignore
    }
    logger.warn(
      `Place Order did not navigate to confirmation: ${String(e)}${reason ? ` | reason: ${reason} (expected, can be ignored)` : ""}`,
    );
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Fill the credit card number field. If the persona's card number does not
 * match the input's pattern attribute, fall back to the default value already
 * present in the field.
 */
async function fillCreditCardNumber(
  pageActions: IPageActions,
  cardNumber: string,
): Promise<void> {
  const handle = await pageActions.getHandle(selectors.creditCardNumber);
  const pattern = await pageActions.getPropertyHandle<string>(
    handle,
    "pattern",
  );
  const defaultValue = await pageActions.getPropertyHandle<string>(
    handle,
    "value",
  );

  const valueToUse =
    pattern && matchesInputPattern(cardNumber, pattern)
      ? cardNumber
      : (defaultValue ?? "");

  await pageActions.inputHandle(handle, valueToUse);
}

function matchesInputPattern(value: string, pattern: string): boolean {
  try {
    return new RegExp(`^(?:${pattern})$`).test(value);
  } catch {
    return true;
  }
}
