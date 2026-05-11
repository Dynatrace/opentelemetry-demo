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
    PAGE_WAIT_UNTIL,
    BROWSER_HEADLESS,
)
from otel_setup import log
from page_actions import (
    order_product,
    inject_headers,
    complete_checkout,
    wait_for_banner,
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
        person = random.choice(people)
        task_id = uuid.uuid4().hex[:8]
        name = fn.__name__
        log.info(
            "[%s] Task started: [%s] ip=[%s] ua=[%s]",
            task_id,
            name,
            person["simulated_ip"],
            person["user_agent"]["label"],
        )

        page.on(
            "console",
            lambda msg: print(msg.text) if msg.type in ("warning", "error") else None,
        )
        await page.route(
            "**/*",
            functools.partial(
                inject_headers,
                spoofed_ip=person["simulated_ip"],
                user_agent=person["user_agent"]["ua"],
            ),
        )
        # Override navigator.userAgent in JS so Dynatrace RUM reports the spoofed
        # UA rather than the real headless Chromium string. add_init_script runs
        # before any page script, so the override is in place before RUM loads.
        await page.add_init_script(
            f"Object.defineProperty(navigator, 'userAgent', {{get: () => {repr(person['user_agent']['ua'])}}});"
        )

        start = time.monotonic()
        try:
            await fn(self, page, person)
            duration = time.monotonic() - start
            log.info(
                "[%s] Task completed: [%s] ip=[%s] ua=[%s] duration=[%.2fs]",
                task_id,
                name,
                person["simulated_ip"],
                person["user_agent"]["label"],
                duration,
            )
        except RescheduleTask:
            raise
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)

    return wrapper


class WebsiteBrowserUser(PlaywrightUser):
    weight = 2
    headless = BROWSER_HEADLESS

    async def _pwprep(self) -> None:
        if self.playwright is None:
            self.playwright = await async_playwright().start()
        if self.browser is None:
            log.info("Browser launched")
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=chromium_base_args,
            )

    @task(1)
    @pw
    @tracked_task
    async def browse_and_checkout(self, page: PageWithRetry, person: dict):
        # Navigate to homepage and wait for banner to let the LCP trigger
        await page.goto("/", wait_until=PAGE_WAIT_UNTIL)
        await wait_for_banner(page)

        # Pick one of the products and add it to cart
        await order_product(page)

        # Use continue shopping to get back to homepage
        async with page.expect_navigation(wait_until=PAGE_WAIT_UNTIL):
            await page.click('button:has-text("Continue Shopping")')
        await wait_for_banner(page)

        # Pick another product
        await order_product(page)

        # Complete checkout
        await complete_checkout(page, person)

        await page.wait_for_timeout(2000)
