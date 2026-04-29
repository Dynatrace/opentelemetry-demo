#!/usr/bin/python
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import functools
import random
import sys
import traceback
import uuid

from locust import task
from locust_plugins.users.playwright import PlaywrightUser, pw, PageWithRetry
from locust.exception import RescheduleTask
from playwright.async_api import async_playwright

from config import (
    chromium_base_args,
    people,
    products,
    PAGE_WAIT_UNTIL,
    simulated_ips,
    user_agents,
)
from otel_setup import log
from page_actions import (
    add_random_quantity_and_add_to_cart,
    inject_headers,
    open_cart_and_go_to_cart_page,
    rum_flush,
    start_on_product_page,
)


class WebsiteBrowserUser(PlaywrightUser):
    weight = 2
    headless = True  # to use a headless browser, without a GUI

    # Class-level defaults ensure copy.copy() (used by PlaywrightUser internally
    # to create sub-users) always finds the attributes. __init__ then sets
    # per-instance values before super().__init__() runs.
    simulated_ip: str = simulated_ips[0]
    user_agent: str = user_agents[0]

    def __init__(self, *args, **kwargs):
        # Must be set before super().__init__() because the parent immediately
        # calls _pwprep() and shallow-copies self to create sub-users.
        self.simulated_ip = random.choice(simulated_ips)
        self.user_agent = random.choice(user_agents)
        super().__init__(*args, **kwargs)

    async def _pwprep(self) -> None:
        if self.playwright is None:
            self.playwright = await async_playwright().start()
        if self.browser is None:
            log.info("Browser launched")
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=chromium_base_args + [f"--user-agent={self.user_agent}"],
            )

    @task(1)
    @pw
    async def open_cart_page_and_change_currency(self, page: PageWithRetry):
        task_id = uuid.uuid4().hex[:8]
        try:
            log.info(
                "[%s] Task started: open_cart_page_and_change_currency ip=%s ua=%s",
                task_id,
                self.simulated_ip,
                self.user_agent,
            )
            await start_on_product_page(page, spoofed_ip=self.simulated_ip)
            await open_cart_and_go_to_cart_page(page)

            checkout_details = random.choice(people)
            await page.select_option(
                '[name="currency_code"]', value=str(checkout_details["userCurrency"])
            )

            await rum_flush(page)
            log.info(
                "[%s] Task completed: open_cart_page_and_change_currency ip=%s ua=%s",
                task_id,
                self.simulated_ip,
                self.user_agent,
            )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)

    @task(1)
    @pw
    async def add_product_to_cart(self, page: PageWithRetry):
        task_id = uuid.uuid4().hex[:8]
        try:
            log.info(
                "[%s] Task started: add_product_to_cart ip=%s ua=%s",
                task_id,
                self.simulated_ip,
                self.user_agent,
            )
            await start_on_product_page(page, spoofed_ip=self.simulated_ip)

            # Add 1-4 products (possibly different product IDs each time)
            for _ in range(random.choice([1, 2, 3, 4])):
                pid = random.choice(products)
                await page.goto(f"/product/{pid}", wait_until=PAGE_WAIT_UNTIL)
                await add_random_quantity_and_add_to_cart(page)

            await open_cart_and_go_to_cart_page(page)
            await rum_flush(page)
            log.info(
                "[%s] Task completed: add_product_to_cart ip=%s ua=%s",
                task_id,
                self.simulated_ip,
                self.user_agent,
            )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)

    @task(3)
    @pw
    async def add_product_to_cart_and_checkout(self, page: PageWithRetry):
        task_id = uuid.uuid4().hex[:8]
        try:
            log.info(
                "[%s] Task started: add_product_to_cart_and_checkout ip=%s ua=%s",
                task_id,
                self.simulated_ip,
                self.user_agent,
            )
            page.on(
                "console",
                lambda msg: (
                    print(msg.text) if msg.type in ("warning", "error") else None
                ),
            )
            await page.route(
                "**/*", functools.partial(inject_headers, spoofed_ip=self.simulated_ip)
            )
            await page.goto("/", wait_until="domcontentloaded")

            # Wait for the banner image to finish loading before interacting with
            # the page. The banner is now fetched via fetch() + blob URL (same
            # pattern as product card images), so its src starts empty and is
            # populated only after the network request completes. Waiting here
            # ensures the browser has had time to record the banner as an LCP
            # candidate before we navigate away. Timeout is 30 s to accommodate
            # intentionally slow loads (imageSlowLoad feature flag / Envoy fault-inject).
            try:
                await page.wait_for_function(
                    "() => { const img = document.querySelector('[data-cy=\"banner-img\"]'); return img && img.src && img.src.startsWith('blob:'); }",
                    timeout=30000,
                )
            except Exception:
                log.warning(
                    "[%s] Banner image did not load within timeout; continuing anyway",
                    task_id,
                )

            # Add 1-4 products to the cart
            for i in range(random.choice([1, 2, 3, 4])):
                product_id = random.choice(products)
                await page.click(f"a[href='/product/{product_id}']")

                product_count = random.choice([3, 4, 5, 8, 9, 10])
                await page.select_option(
                    'select[data-cy="product-quantity"]', value=str(product_count)
                )

                await page.click('button:has-text("Add To Cart")')
                await page.click('button:has-text("Continue Shopping")')

            # Open the Shopping cart flyout
            await page.click('a[data-cy="cart-icon"]')
            await page.click('button:has-text("Go to Shopping Cart")')

            checkout_details = random.choice(people)
            await page.select_option(
                'select[name="currency_code"]',
                value=str(checkout_details["userCurrency"]),
            )

            await page.locator("input#email").fill(checkout_details["email"])
            await page.locator("input#street_address").fill(
                checkout_details["address"]["streetAddress"]
            )
            await page.locator("input#zip_code").fill(
                str(checkout_details["address"]["zipCode"])
            )
            await page.locator("input#city").fill(checkout_details["address"]["city"])
            await page.locator("input#state").fill(checkout_details["address"]["state"])
            await page.locator("input#country").fill(
                checkout_details["address"]["country"]
            )
            await page.locator("input#credit_card_number").fill(
                str(checkout_details["creditCard"]["creditCardNumber"])
            )
            await page.select_option(
                "select#credit_card_expiration_month",
                value=str(checkout_details["creditCard"]["creditCardExpirationMonth"]),
            )
            await page.select_option(
                "select#credit_card_expiration_year",
                value=str(checkout_details["creditCard"]["creditCardExpirationYear"]),
            )
            await page.locator("input#credit_card_cvv").fill(
                str(checkout_details["creditCard"]["creditCardCvv"])
            )

            await page.click('button:has-text("Place Order")')
            await page.wait_for_timeout(
                8000
            )  # giving the browser time to export the traces
            log.info(
                "[%s] Task completed: add_product_to_cart_and_checkout ip=%s ua=%s",
                task_id,
                self.simulated_ip,
                self.user_agent,
            )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)

    @task(1)
    @pw
    async def view_product_page(self, page: PageWithRetry):
        task_id = uuid.uuid4().hex[:8]
        try:
            log.info(
                "[%s] Task started: view_product_page ip=%s ua=%s",
                task_id,
                self.simulated_ip,
                self.user_agent,
            )
            pid = random.choice(
                ["0PUK6V6EV0", "1YMWWN1N4O", "2ZYFJ3GM2N", "66VCHSJNUP"]
            )
            await start_on_product_page(
                page, product_id=pid, spoofed_ip=self.simulated_ip
            )
            await rum_flush(page)
            log.info(
                "[%s] Task completed: view_product_page ip=%s ua=%s",
                task_id,
                self.simulated_ip,
                self.user_agent,
            )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)
