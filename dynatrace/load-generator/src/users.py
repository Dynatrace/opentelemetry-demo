#!/usr/bin/python
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import functools
import random
import sys
import time
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
    wait_for_banner,
    wait_for_product_card,
)


def tracked_task(fn):
    """Decorator for @pw task coroutines.

    Automatically:
    - Registers a console warning/error listener on the page
    - Installs the header injection route (X-Forwarded-For + baggage)
    - Generates a short task_id for log correlation
    - Logs task start and completion (with duration in seconds)
    - Catches exceptions, prints the traceback, and raises RescheduleTask
    """

    @functools.wraps(fn)
    async def wrapper(self, page: PageWithRetry):
        task_id = uuid.uuid4().hex[:8]
        name = fn.__name__
        log.info(
            "[%s] Task started: [%s] ip=[%s] ua=[%s]",
            task_id,
            name,
            self.simulated_ip,
            self.user_agent["label"],
        )

        page.on(
            "console",
            lambda msg: print(msg.text) if msg.type in ("warning", "error") else None,
        )
        await page.route(
            "**/*", functools.partial(inject_headers, spoofed_ip=self.simulated_ip)
        )

        start = time.monotonic()
        try:
            await fn(self, page)
            duration = time.monotonic() - start
            log.info(
                "[%s] Task completed: [%s] ip=[%s] ua=[%s] duration=[%.2fs]",
                task_id,
                name,
                self.simulated_ip,
                self.user_agent["label"],
                duration,
            )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)

    return wrapper


class WebsiteBrowserUser(PlaywrightUser):
    weight = 2
    headless = True  # to use a headless browser, without a GUI

    # Class-level defaults ensure copy.copy() (used by PlaywrightUser internally
    # to create sub-users) always finds the attributes. __init__ then sets
    # per-instance values before super().__init__() runs.
    simulated_ip: str = simulated_ips[0]
    user_agent: dict = user_agents[0]

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
                args=chromium_base_args + [f"--user-agent={self.user_agent['ua']}"],
            )

    # @task(1)
    # @pw
    # @tracked_task
    # async def open_cart_page_and_change_currency(self, page: PageWithRetry):
    #     await start_on_product_page(page)
    #     await open_cart_and_go_to_cart_page(page)

    #     checkout_details = random.choice(people)
    #     await page.select_option(
    #         '[name="currency_code"]', value=str(checkout_details["userCurrency"])
    #     )

    #     await rum_flush(page)

    # @task(1)
    # @pw
    # @tracked_task
    # async def add_product_to_cart(self, page: PageWithRetry):
    #     await start_on_product_page(page)

    #     # Add 1-4 products (possibly different product IDs each time)
    #     for _ in range(random.choice([1, 2, 3, 4])):
    #         pid = random.choice(products)
    #         await page.goto(f"/product/{pid}", wait_until=PAGE_WAIT_UNTIL)
    #         await page.wait_for_timeout(1000)  # flat 1s wait for subsequent navigations
    #         await add_random_quantity_and_add_to_cart(page)

    #     await open_cart_and_go_to_cart_page(page)
    #     await rum_flush(page)

    @task(3)
    @pw
    @tracked_task
    async def add_product_to_cart_and_checkout(self, page: PageWithRetry):
        await page.goto("/", wait_until=PAGE_WAIT_UNTIL)

        await wait_for_banner(page)

        # Add 1-4 products to the cart
        for _ in range(random.choice([1, 2])):
            product_id = random.choice(products)
            await page.click(f"a[href='/product/{product_id}']")
            await page.wait_for_timeout(1000)  # flat 1s wait for subsequent navigations
            await page.select_option(
                'select[data-cy="product-quantity"]',
                value=str(random.choice([3, 4, 5, 8, 9, 10])),
            )
            await page.click('button:has-text("Add To Cart")')
            await page.click('button:has-text("Continue Shopping")')

        # Open the Shopping cart flyout and proceed to checkout
        await page.click('a[data-cy="cart-icon"]')
        await page.click('button:has-text("Go to Shopping Cart")')

        checkout_details = random.choice(people)
        await page.select_option(
            'select[name="currency_code"]', value=str(checkout_details["userCurrency"])
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
        await page.locator("input#country").fill(checkout_details["address"]["country"])
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

    # @task(1)
    # @pw
    # @tracked_task
    # async def view_product_page(self, page: PageWithRetry):
    #     pid = random.choice(["0PUK6V6EV0", "1YMWWN1N4O", "2ZYFJ3GM2N", "66VCHSJNUP"])
    #     await start_on_product_page(page, product_id=pid)
    #     await rum_flush(page)
