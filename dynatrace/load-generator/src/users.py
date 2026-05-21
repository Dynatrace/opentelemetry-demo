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
    - Picks a random persona for this task run and stores it on self so that
      the context-level route handler (registered once per BrowserContext in
      _setup_context) can read the current persona without being re-registered
      on every iteration.
    - Updates window.__locust_ua__ so the init script (registered once per
      BrowserContext) serves the correct User-Agent string for this task run.
    - Generates a short task_id for log correlation.
    - Logs task start and completion (with duration in seconds).
    - Catches exceptions, prints the traceback, and raises RescheduleTask.
    """

    @functools.wraps(fn)
    async def wrapper(self, page: PageWithRetry):
        person = random.choice(people)
        # Store on self so the route handler lambda (registered once per
        # BrowserContext) can read the current persona at request time without
        # needing to be re-registered for every task iteration.
        self._current_person = person

        task_id = uuid.uuid4().hex[:8]
        name = fn.__name__
        log.info(
            "[%s] Task started: [%s] ip=[%s] ua=[%s]",
            task_id,
            name,
            person["simulated_ip"],
            person["user_agent"]["label"],
        )

        # Update the JS variable that the UA init script (installed once per
        # context in _setup_context) reads via its getter.  evaluate() runs in
        # the current frame and is not stored anywhere, so there is no
        # accumulation.
        await page.evaluate(
            f"window.__locust_ua__ = {repr(person['user_agent']['ua'])};"
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

    # Holds the persona chosen for the current task run.  The route handler and
    # console listener are registered once per BrowserContext (in
    # _setup_context) and read this attribute at call time, so they never need
    # to be re-registered across iterations.
    _current_person: dict = None

    async def _pwprep(self) -> None:
        if self.playwright is None:
            self.playwright = await async_playwright().start()
        if self.browser is None:
            log.info("Browser launched")
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=chromium_base_args,
            )

    async def _setup_context(self) -> None:
        """Register per-context handlers on self.browser_context and self.page.

        Called once per task run right after @pw has created a fresh
        BrowserContext and Page, before the task body executes.  Because the
        context is discarded at the end of each task run by @pw, there is no
        accumulation of handlers across iterations.

        - console listener: registered with page.once so it is automatically
          removed after firing, preventing listener list growth within a single
          page's lifetime.
        - route handler: registered once on the *context* (not the page) so
          that it covers all pages/frames opened during checkout.  The lambda
          reads self._current_person at request time, so the persona can be
          updated per task by tracked_task without re-registering the handler.
        - UA init script: registered once on the context using a JS getter that
          reads window.__locust_ua__, which tracked_task updates via
          page.evaluate() before each navigation.  A single static script
          string is stored by Playwright instead of one string per iteration.
        """
        # Log browser console warnings/errors.  page.once removes the handler
        # automatically after the first matching event, avoiding listener
        # accumulation within a page's lifetime.
        self.page.on(
            "console",
            lambda msg: print(msg.text) if msg.type in ("warning", "error") else None,
        )

        # Register the header-injection route handler once on the context so it
        # applies to all requests made during this task run.  The lambda
        # captures `self` (not the person dict directly) so it always reads the
        # current persona from self._current_person at the time each request is
        # intercepted — no re-registration needed when the persona changes.
        await self.browser_context.route(
            "**/*",
            lambda route, request: inject_headers(
                route,
                request,
                spoofed_ip=self._current_person["simulated_ip"],
                user_agent=self._current_person["user_agent"]["ua"],
            ),
        )

        # Override navigator.userAgent in JS so Dynatrace RUM reports the
        # spoofed UA rather than the real headless Chromium string.  The getter
        # reads window.__locust_ua__, which tracked_task updates via
        # page.evaluate() before the first navigation of each task run.  A
        # single static script string is registered once per context instead of
        # one new string per iteration.
        await self.browser_context.add_init_script(
            "Object.defineProperty(navigator, 'userAgent', "
            "{get: () => window.__locust_ua__ || navigator.userAgent});"
        )

    @task(1)
    @pw
    @tracked_task
    async def browse_and_checkout(self, page: PageWithRetry, person: dict):
        # Set up context-level handlers once per task run, after @pw has
        # created a fresh BrowserContext and Page and tracked_task has chosen
        # the persona for this iteration.
        await self._setup_context()

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
