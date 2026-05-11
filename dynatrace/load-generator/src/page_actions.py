#!/usr/bin/python
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import logging
import random

from locust_plugins.users.playwright import PageWithRetry
from playwright.async_api import Route, Request

from config import PAGE_WAIT_UNTIL, SYNTHETIC_REQUEST_ENABLED

log = logging.getLogger("loadgen")


async def inject_headers(
    route: Route, request: Request, spoofed_ip: str, user_agent: str
):
    """Inject X-Forwarded-For for geolocation simulation, a real browser User-Agent
    to avoid headless bot detection, and, when SYNTHETIC_REQUEST_ENABLED is set,
    synthetic_request=true in the W3C baggage header so the frontend SSR flags the
    session correctly. Set SYNTHETIC_REQUEST_ENABLED=false on HTTPS deployments where
    the internal collector URL is unreachable from the browser (Mixed Content)."""
    existing_baggage = request.headers.get("baggage", "")
    extra_baggage = "synthetic_request=true" if SYNTHETIC_REQUEST_ENABLED else ""
    headers = {
        **request.headers,
        "X-Forwarded-For": spoofed_ip,
        "User-Agent": user_agent,
        "baggage": ", ".join(filter(None, (existing_baggage, extra_baggage))),
    }
    await route.continue_(headers=headers)


async def wait_for_banner(page: PageWithRetry, timeout: int = 15000):
    """Wait until the banner <img data-cy="banner-img"> has fully loaded.

    The banner fetches its image via fetch(), converts the response to a blob
    URL and sets it as the src of an <img> tag. naturalWidth > 0 becomes true
    only after the browser has decoded the image.
    """
    try:
        await page.wait_for_function(
            """() => {
                const img = document.querySelector('[data-cy="banner-img"]');
                return img && img.naturalWidth > 0;
            }""",
            timeout=timeout,
        )
    except Exception:
        pass


async def wait_for_product_card(page: PageWithRetry, timeout: int = 15000):
    """Wait until at least one product-card image has loaded.

    ProductCard sets its image as a CSS background via a styled-components class
    (not an inline style), so getComputedStyle is required. The function resolves
    as soon as the first card's computed backgroundImage is set to any non-none
    value, which happens once the blob URL is injected into the generated class.
    """
    try:
        await page.wait_for_function(
            """() => {
                const els = document.querySelectorAll('[data-cy="product-card"]');
                return Array.from(els).some(el => {
                    const bg = getComputedStyle(el).backgroundImage;
                    return bg && bg !== 'none' && bg !== '';
                });
            }""",
            timeout=timeout,
        )
    except Exception:
        pass

async def order_product(page: PageWithRetry):
    cards = await page.query_selector_all('[data-cy="product-card"]')
    card = random.choice(cards)
    await card.scroll_into_view_if_needed()
    await page.wait_for_timeout(1000)
    async with page.expect_navigation(wait_until=PAGE_WAIT_UNTIL):
        await card.click()
    await page.wait_for_timeout(2000)
    await page.select_option(
        'select[data-cy="product-quantity"]',
        value=str(random.choice([1, 2, 3, 4, 5, 10])),
    )
    await page.wait_for_timeout(1000)
    async with page.expect_navigation(wait_until=PAGE_WAIT_UNTIL):
        await page.click('button:has-text("Add To Cart")')

async def complete_checkout(page: PageWithRetry, person: dict):
    # add a timeout between each action to make the replay look slightly better
    action_duration = 100
    await page.select_option(
        'select[name="currency_code"]', value=str(person["userCurrency"])
    )
    await page.wait_for_timeout(action_duration)
    await page.locator("input#email").fill(person["email"])
    await page.wait_for_timeout(action_duration)
    await page.locator("input#street_address").fill(
        person["address"]["streetAddress"]
    )
    await page.wait_for_timeout(action_duration)
    await page.locator("input#zip_code").fill(str(person["address"]["zipCode"]))
    await page.wait_for_timeout(action_duration)
    await page.locator("input#city").fill(person["address"]["city"])
    await page.wait_for_timeout(action_duration)
    await page.locator("input#state").fill(person["address"]["state"])
    await page.wait_for_timeout(action_duration)
    await page.locator("input#country").fill(person["address"]["country"])
    await page.wait_for_timeout(action_duration)
    await page.locator("input#credit_card_number").fill(
        str(person["creditCard"]["creditCardNumber"])
    )
    await page.wait_for_timeout(action_duration)
    await page.select_option(
        "select#credit_card_expiration_month",
        value=str(person["creditCard"]["creditCardExpirationMonth"]),
    )
    await page.wait_for_timeout(action_duration)
    await page.select_option(
        "select#credit_card_expiration_year",
        value=str(person["creditCard"]["creditCardExpirationYear"]),
    )
    await page.wait_for_timeout(action_duration)
    await page.locator("input#credit_card_cvv").fill(
        str(person["creditCard"]["creditCardCvv"])
    )
    await page.wait_for_timeout(action_duration)
    await page.click('button:has-text("Place Order")')
    try:
        await page.wait_for_url("**/cart/checkout/**", timeout=5000)
    except Exception as e:
        # Navigation did not occur within 5 s. Inspect the page for a visible reason.
        reason = None
        try:
            # Browser HTML5 validation popups (e.g. "Please match the requested format")
            # leave the form visible and set a validationMessage on the invalid field.
            invalid = await page.evaluate("""() => {
                const els = [...document.querySelectorAll('input:invalid, select:invalid, textarea:invalid')];
                if (!els.length) return null;
                return els.map(el => {
                    const id = el.id || el.name || el.placeholder || el.tagName.toLowerCase();
                    return `${id}: ${el.validationMessage || '(no message)'}`;
                }).join('; ');
            }""")
            if invalid:
                reason = f"form validation error — {invalid}"
            else:
                # Look for any visible error/alert text rendered by the app itself.
                el = page.locator('[role="alert"], .error, [data-cy="error"]').first
                if await el.is_visible(timeout=500):
                    reason = f"page error — {await el.inner_text()}"
        except Exception:
            pass
        log.warning(
            "Place Order did not navigate to confirmation: %s: %s%s",
            type(e).__name__,
            e,
            f" | reason: {reason}" if reason else "",
        )
