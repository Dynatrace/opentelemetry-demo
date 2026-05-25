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
    - Picks a random persona for this task run and stores it on self so that
      _setup_context() can read it when setting extra HTTP headers.
    - Calls _setup_context() to register the init script, set headers, and
      attach the console listener — before the task body runs.
    - Updates window.__locust_ua__ so the init script serves the correct
      User-Agent string for this task run.
    - Generates a short task_id for log correlation.
    - Logs task start and completion (with duration in seconds).
    - Catches exceptions, prints the traceback, and raises RescheduleTask.
    """

    @functools.wraps(fn)
    async def wrapper(self, page: PageWithRetry):
        person = random.choice(people)
        # Store on self so _setup_context() can read the current persona
        # when building the set_extra_http_headers() dict.
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

        # Configure the fresh BrowserContext and Page that @pw just created:
        # installs the navigator.userAgent init script on the context, sets
        # extra HTTP headers, and registers the console listener.  Must run
        # before any navigation so that add_init_script() fires on the first
        # page.goto() call inside the task body.
        await self._setup_context()

        # Update the JS variable that the UA init script (installed above by
        # _setup_context) reads via its getter.  Must run after _setup_context
        # (which registers the init script) and before the first navigation
        # (which executes it).
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

    # Holds the persona chosen for the current task run so _setup_context()
    # can read it when building the set_extra_http_headers() dict.
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
        """Configure the BrowserContext and Page created by @pw for this task run.

        Called by tracked_task's wrapper before the task body executes, after
        @pw has created a fresh BrowserContext and Page and the persona has been
        chosen.  Ordering guarantee: _setup_context() runs before page.evaluate()
        (which sets window.__locust_ua__) and before the first page.goto(), so
        add_init_script() is always registered before the first navigation fires it.

        Headers (X-Forwarded-For, User-Agent, optionally baggage) are injected via
        set_extra_http_headers(), which sends a single CDP command per context
        and requires zero per-request callbacks.  This avoids the asyncio
        Task / Future / Request object churn that context.route() causes for
        every intercepted network request — which was the confirmed source of
        unbounded Python-process memory growth.

        navigator.userAgent is overridden via a single add_init_script() on the
        context; the script reads window.__locust_ua__ which tracked_task sets
        via page.evaluate() immediately after this method returns.
        """
        # Log browser console warnings/errors once per page lifetime.
        self.page.on(
            "console",
            lambda msg: print(msg.text) if msg.type in ("warning", "error") else None,
        )

        # Inject geolocation and UA headers without route interception.
        # set_extra_http_headers() sends one CDP setExtraHTTPHeaders command;
        # it does not register any per-request callbacks and creates no
        # asyncio Tasks, Futures, or Request objects per network request.
        # X-Forwarded-For: browsers never send this header themselves, so
        # there is nothing to merge — the value is always ours alone.
        # User-Agent: we want to replace the HeadlessChrome UA entirely.
        # baggage: synthetic_request=true flags SSR to route browser-side OTLP
        # traces to the internal collector; disabled via SYNTHETIC_REQUEST_ENABLED=false
        # on HTTPS deployments where the internal collector URL is unreachable (Mixed Content).
        headers = {
            "X-Forwarded-For": self._current_person["simulated_ip"],
            "User-Agent": self._current_person["user_agent"]["ua"],
        }
        if SYNTHETIC_REQUEST_ENABLED:
            headers["baggage"] = "synthetic_request=true"
        await self.browser_context.set_extra_http_headers(headers)

        # Override navigator.userAgent in JS so Dynatrace RUM reports the
        # spoofed UA rather than the real headless Chromium string.  The getter
        # reads window.__locust_ua__, which tracked_task updates via
        # page.evaluate() before the first navigation of each task run.  A
        # single static script string is registered once per context instead of
        # one new string per iteration.
        await self.browser_context.add_init_script(
            "(function(){"
            "var _orig=navigator.userAgent;"
            "Object.defineProperty(navigator,'userAgent',"
            "{get:function(){return window.__locust_ua__||_orig;}});"
            "}());"
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
