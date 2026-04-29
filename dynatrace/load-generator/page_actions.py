#!/usr/bin/python
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import functools

from locust_plugins.users.playwright import PageWithRetry
from playwright.async_api import Route, Request

from config import PAGE_WAIT_UNTIL, RUM_FLUSH_MS, products


async def inject_headers(route: Route, request: Request, spoofed_ip: str):
    """Inject X-Forwarded-For for geolocation simulation and synthetic_request=true
    in the W3C baggage header so the frontend SSR flags the session correctly."""
    existing_baggage = request.headers.get("baggage", "")
    headers = {
        **request.headers,
        "X-Forwarded-For": spoofed_ip,
        "baggage": ", ".join(
            filter(None, (existing_baggage, "synthetic_request=true"))
        ),
    }
    await route.continue_(headers=headers)


async def start_on_product_page(
    page: PageWithRetry, product_id: str | None = None, spoofed_ip: str | None = None
) -> str:
    import random

    page.on(
        "console",
        lambda msg: print(msg.text) if msg.type in ("warning", "error") else None,
    )
    if spoofed_ip is not None:
        await page.route(
            "**/*", functools.partial(inject_headers, spoofed_ip=spoofed_ip)
        )

    pid = product_id or random.choice(products)
    await page.goto(f"/product/{pid}", wait_until=PAGE_WAIT_UNTIL)

    try:
        await page.wait_for_selector('button:has-text("Add To Cart")', timeout=8000)
    except Exception:
        pass
    return pid


async def rum_flush(page: PageWithRetry, ms: int = RUM_FLUSH_MS):
    await page.wait_for_timeout(ms)


async def add_random_quantity_and_add_to_cart(page: PageWithRetry):
    import random

    try:
        await page.select_option(
            'select[data-cy="product-quantity"]',
            value=str(random.choice([1, 2, 3, 4, 5, 10])),
        )
    except Exception:
        pass

    await page.click('button:has-text("Add To Cart")', timeout=6000)

    try:
        await page.click('button:has-text("Continue Shopping")', timeout=6000)
    except Exception:
        pass


async def open_cart_and_go_to_cart_page(page: PageWithRetry):
    try:
        await page.click('a[data-cy="cart-icon"]', timeout=6000)

        try:
            async with page.expect_navigation(timeout=8000):
                await page.click('button:has-text("Go to Shopping Cart")', timeout=6000)
        except Exception:
            try:
                await page.wait_for_url("**/cart**", timeout=8000)
            except Exception:
                pass
    except Exception:
        pass
