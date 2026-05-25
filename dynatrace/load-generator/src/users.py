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
      _setup_context() can read it when building the route handler and init script.
    - Calls _setup_context() to register the UA init script, set extra HTTP
      headers, and attach the console listener — before the task body runs.
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

        Headers are injected in two ways to avoid CORS preflight failures on
        cross-origin requests (e.g. Google Fonts):
        - User-Agent: via set_extra_http_headers() — it is a CORS-safelisted
          header so it never triggers a preflight on cross-origin requests.
        - X-Forwarded-For + baggage: via a same-origin-scoped context.route()
          handler — route.continue_() injects headers after the browser has
          already dispatched the CORS preflight without them, so third-party
          servers are never affected.  The handler only intercepts same-origin
          requests (~50–60/page), reducing Task/Future churn ~8× vs the old
          "**/*" route handler that intercepted every request (~465/task).

        navigator.userAgent is overridden via a single add_init_script() on the
        context; the script reads window.__locust_ua__ which tracked_task sets
        via page.evaluate() immediately after this method returns.
        """
        # Log browser console warnings/errors once per page lifetime.
        self.page.on(
            "console",
            lambda msg: print(msg.text) if msg.type in ("warning", "error") else None,
        )

        # User-Agent is a CORS-safelisted request header — browsers always send
        # it, so adding it via set_extra_http_headers() never triggers a CORS
        # preflight on cross-origin requests.
        await self.browser_context.set_extra_http_headers({
            "User-Agent": self._current_person["user_agent"]["ua"],
        })

        # X-Forwarded-For and baggage are NOT CORS-safelisted.  Sending them via
        # set_extra_http_headers() causes the browser to include them in CORS
        # preflight requests to cross-origin servers (e.g. Google Fonts), which
        # reject the preflight because they don't whitelist these headers.
        # Unlike set_extra_http_headers(), Playwright's route.continue_() injects
        # headers after the browser has already committed to the request — CORS
        # preflight for cross-origin requests has already been sent without these
        # headers, so third-party servers are unaffected.
        # We therefore use a same-origin-scoped route handler for these two headers
        # only, keeping cross-origin requests completely unmodified.
        #
        # Memory-leak risk: the original leak was route("**/*") intercepting ~465
        # requests/task.  This handler matches only same-origin requests
        # (~50–60/page), so the Task/Future churn is reduced ~8× vs the old code.
        # The remaining Tasks are short-lived and are reaped normally.
        _ip = self._current_person["simulated_ip"]
        _extra: dict = {"X-Forwarded-For": _ip}
        if SYNTHETIC_REQUEST_ENABLED:
            _extra["baggage"] = "synthetic_request=true"

        async def _inject_same_origin(route, request):
            await route.continue_(headers={**request.headers, **_extra})

        await self.browser_context.route(
            self.host.rstrip("/") + "/**",
            _inject_same_origin,
        )

        # Override navigator.userAgent in JS so Dynatrace RUM reports the
        # spoofed UA rather than the real headless Chromium string.
        # The UA value is embedded directly into the init script — it is baked
        # in at context creation time (persona is already chosen by tracked_task
        # before _setup_context is called) and fires atomically on every new
        # document, before any page script runs.  This avoids the window.__locust_ua__
        # indirection, which was unreliable because page.evaluate() sets a variable
        # on the *current* document; after page.goto() the new document starts
        # fresh and window.__locust_ua__ would be undefined again.
        _ua_json = repr(self._current_person["user_agent"]["ua"])
        await self.browser_context.add_init_script(
            f"(function(){{"
            f"var _ua={_ua_json};"
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
