#!/usr/bin/python
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import functools
import json
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
    SYNTHETIC_REQUEST_ENABLED,
)
from otel_setup import log
from page_actions import (
    order_product,
    complete_checkout,
    wait_for_banner,
)


def tracked_task(fn):
    """Decorator for @pw task coroutines.

    Automatically:
    - Picks a random persona for this task run and passes it to _setup_context().
    - Calls _setup_context() to register the UA init script, set extra HTTP
      headers, and attach the console listener — before the task body runs.
    - Generates a short task_id for log correlation.
    - Logs task start and completion (with duration in seconds).
    - Catches exceptions, prints the traceback, and raises RescheduleTask.
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

        # Configure the fresh BrowserContext and Page that @pw just created:
        # installs the navigator.userAgent init script on the context, sets
        # extra HTTP headers, and registers the console listener.  Must run
        # before any navigation so that add_init_script() fires on the first
        # page.goto() call inside the task body.
        await self._setup_context(person)

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

    async def _setup_context(self, person: dict) -> None:
        """Configure the BrowserContext and Page created by @pw for this task run.

        Called by tracked_task's wrapper before the task body executes, after
        @pw has created a fresh BrowserContext and Page and the persona has been
        chosen.

        All headers are injected via set_extra_http_headers(), which sends a
        single CDP setExtraHTTPHeaders command per context and creates zero
        per-request Python callbacks, asyncio Tasks, or RouteHandler objects.

        This is the only viable approach given the gevent↔asyncio bridge used by
        locust-plugins.  context.route() causes pyee to call ensure_future() for
        every intercepted request; those Tasks are never reaped by the asyncio
        event loop while gevent holds the GIL, leading to unbounded growth of
        Task, Future, RouteHandler, and BrowserContext objects.

        Side effect: X-Forwarded-For is a non-CORS-safelisted header, so the
        browser includes it in preflight requests to cross-origin servers
        (e.g. Google Fonts).  Those servers reject the preflight with a CORS
        error, causing font load failures.  This is cosmetic — the app renders
        correctly without the font, and Dynatrace RUM is unaffected because all
        RUM beacon (/rb_*) requests go to the same origin.  The console listener
        below suppresses these known-harmless errors to keep logs clean.
        """
        # Suppress known-harmless cross-origin CORS errors caused by
        # X-Forwarded-For triggering preflight rejections on Google Fonts.
        # The CORS block emits two console messages: one containing the domain
        # name and one generic "Failed to load resource: net::ERR_FAILED" with
        # no URL.  Both are suppressed; all other warnings/errors are printed.
        _suppress = ("fonts.googleapis.com", "fonts.gstatic.com", "Failed to load resource")
        self.page.on(
            "console",
            lambda msg: (
                print(msg.text)
                if msg.type in ("warning", "error")
                and not any(s in msg.text for s in _suppress)
                else None
            ),
        )

        # Inject all headers at context level via a single CDP command.
        # No route handlers — no per-request Task/Future churn.
        headers = {
            "X-Forwarded-For": person["simulated_ip"],
            "User-Agent": person["user_agent"]["ua"],
        }
        if SYNTHETIC_REQUEST_ENABLED:
            headers["baggage"] = "synthetic_request=true"
        await self.browser_context.set_extra_http_headers(headers)

        # Override navigator.userAgent in JS so Dynatrace RUM reports the
        # spoofed UA rather than the real headless Chromium string.
        # The UA value is embedded directly into the init script — it fires
        # atomically on every new document before any page script runs.
        # json.dumps() produces a properly escaped JS string literal.
        await self.browser_context.add_init_script(
            f"(function(){{"
            f"var _ua={json.dumps(person['user_agent']['ua'])};"
            f"Object.defineProperty(navigator,'userAgent',{{get:function(){{return _ua;}}}});"
            f"}}());"
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
