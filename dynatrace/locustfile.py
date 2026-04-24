#!/usr/bin/python
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import random
import sys
import traceback
import uuid
import logging
import functools

from locust import HttpUser, task, between
from locust_plugins.users.playwright import PlaywrightUser, pw, PageWithRetry, event
from locust.exception import RescheduleTask  # added explicitly

from opentelemetry import context, baggage, trace
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.jinja2 import Jinja2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter,
)
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

from openfeature import api
from openfeature.contrib.provider.ofrep import OFREPProvider
from openfeature.contrib.hook.opentelemetry import TracingHook

from playwright.async_api import async_playwright, Route, Request

logger_provider = LoggerProvider(resource=Resource.create(
    {
        "service.name": "load-generator",
    }
))
set_logger_provider(logger_provider)
exporter = OTLPLogExporter(insecure=True)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

# Attach OTLP handler to locust logger
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)

# Named logger with its own StreamHandler so our messages are visible in the
# terminal regardless of how Locust reconfigures the root logger after startup.
log = logging.getLogger("loadgen")
log.setLevel(logging.INFO)
log.propagate = False  # don't double-emit through root
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setLevel(logging.INFO)
_stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s"))
log.addHandler(_stream_handler)
log.addHandler(handler)  # also forward to OTLP

exporter = OTLPMetricExporter(insecure=True)
set_meter_provider(MeterProvider([PeriodicExportingMetricReader(exporter)]))

tracer_provider = TracerProvider()
trace.set_tracer_provider(tracer_provider)
tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

# Instrumenting manually to avoid error with locust gevent monkey
Jinja2Instrumentor().instrument()
RequestsInstrumentor().instrument()
SystemMetricsInstrumentor().instrument()
URLLib3Instrumentor().instrument()
logging.info("Instrumentation complete")

# Initialize Flagd provider
base_url = f"http://{os.environ.get('FLAGD_HOST', 'localhost')}:{os.environ.get('FLAGD_OFREP_PORT', 8016)}"
api.set_provider(OFREPProvider(base_url=base_url))
api.add_hooks([TracingHook()])

def get_flagd_value(FlagName):
    # Initialize OpenFeature    
    client = api.get_client()
    return client.get_integer_value(FlagName, 0)

categories = [
    "binoculars",
    "telescopes",
    "accessories",
    "assembly",
    "travel",
    "books",
    None,
]

products = [
    "0PUK6V6EV0",
    "1YMWWN1N4O",
    "2ZYFJ3GM2N",
    "66VCHSJNUP",
    "6E92ZMYYFZ",
    "9SIQT8TOJO",
    "L9ECAV7KIM",
    "LS4PSXUNUM",
    "OLJCESPC7Z",
    "HQTGWGPNH4",
]

people_file = open('people.json')
people = json.load(people_file)

PAGE_WAIT_UNTIL = os.environ.get("PAGE_WAIT_UNTIL", "load")
if PAGE_WAIT_UNTIL not in ("load", "domcontentloaded", "commit", "networkidle"):
    PAGE_WAIT_UNTIL = "load"

RUM_FLUSH_MS = int(os.environ.get("RUM_FLUSH_MS", "8000"))

# Pool of public IPs representing real cities across multiple continents.
# Dynatrace resolves geolocation from the IP on RUM beacon requests (/rb_*).
# Each virtual user picks one IP for its entire lifetime so all its sessions
# appear to originate from a consistent location rather than a random per-click one.
simulated_ips = [
    # North America
    "8.8.8.8",          # Google DNS      – Mountain View, CA, US
    "204.79.197.200",   # Bing            – Seattle, WA, US
    "198.41.0.4",       # Cloudflare      – New York, NY, US
    "192.0.2.10",       # TEST-NET        – Chicago, IL, US
    "64.233.160.0",     # Google          – Atlanta, GA, US
    "23.185.0.3",       # Fastly CDN      – Denver, CO, US
    "96.7.128.0",       # Akamai          – Dallas, TX, US
    "208.67.222.222",   # OpenDNS         – San Jose, CA, US
    # Europe
    "185.60.216.35",    # Facebook        – Dublin, IE
    "195.51.195.1",     #                 – Amsterdam, NL
    "81.2.69.160",      #                 – London, GB
    "77.75.77.24",      #                 – Prague, CZ
    "31.13.64.35",      # Facebook        – Frankfurt, DE
    "194.165.16.11",    #                 – Warsaw, PL
    "193.0.14.129",     # RIPE NCC        – Amsterdam, NL
    "212.58.244.20",    # BBC             – London, GB
    # Asia-Pacific
    "203.208.43.1",     # Google Japan    – Tokyo, JP
    "180.76.76.76",     # Baidu DNS       – Beijing, CN
    "202.12.27.33",     # APNIC           – Brisbane, AU
    "103.86.96.100",    #                 – Singapore
    "117.18.232.200",   #                 – Mumbai, IN
    "168.126.63.1",     # KT Corp         – Seoul, KR
    # Latin America
    "200.221.11.100",   #                 – São Paulo, BR
    "201.159.177.1",    #                 – Mexico City, MX
    # Middle East / Africa
    "41.206.26.0",      #                 – Lagos, NG
    "196.202.45.1",     #                 – Nairobi, KE
]

# Headless Chromium advertises "HeadlessChrome" in its User-Agent string, which
# Dynatrace's udger.com-based bot detection classifies as a Robot. Passing
# --user-agent at browser launch replaces it with a real browser UA so sessions
# appear as genuine user traffic in Dynatrace RUM / Digital Experience.
# Each virtual user picks one UA for its entire lifetime so all its sessions
# appear to originate from a consistent browser rather than a random per-click one.
user_agents = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    # Edge on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.3912.72",
]

chromium_base_args = [
    "--disable-gpu",
    "--disable-setuid-sandbox",
    "--disable-accelerated-2d-canvas",
    "--no-zygote",
    "--frame-throttle-fps=10",
    "--disable-blink-features=AutomationControlled",
    "--disable-blink-features",
    "--disable-translate",
    "--safebrowsing-disable-auto-update",
    "--disable-sync",
    "--hide-scrollbars",
    "--disable-notifications",
    "--disable-logging",
    "--disable-permissions-api",
    "--ignore-certificate-errors",
    "--proxy-server='direct://'",
    "--proxy-bypass-list=*",
    "--no-first-run",
    "--disable-audio-output",
    "--disable-canvas-aa",
]

async def inject_headers(route: Route, request: Request, spoofed_ip: str):
    """Inject X-Forwarded-For for geolocation simulation and synthetic_request=true
    in the W3C baggage header so the frontend SSR flags the session correctly."""
    existing_baggage = request.headers.get('baggage', '')
    headers = {
        **request.headers,
        "X-Forwarded-For": spoofed_ip,
        "baggage": ', '.join(filter(None, (existing_baggage, 'synthetic_request=true'))),
    }
    await route.continue_(headers=headers)

async def start_on_product_page(page: PageWithRetry, product_id: str | None = None, spoofed_ip: str | None = None) -> str:

    page.on("console", lambda msg: print(msg.text) if msg.type in ("warning", "error") else None)
    await page.route('**/*', functools.partial(inject_headers, spoofed_ip=spoofed_ip))

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
    try:
        await page.select_option('select[data-cy="product-quantity"]',
                                 value=str(random.choice([1, 2, 3, 4, 5, 10])))
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

class WebsiteBrowserUser(PlaywrightUser):
    weight = 2
    headless = True  #to use a headless browser, without a GUI

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
            log.info("Session started: ip=%s ua=%s", self.simulated_ip, self.user_agent)
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=chromium_base_args + [f"--user-agent={self.user_agent}"],
            )

    @task(1)
    @pw
    async def open_cart_page_and_change_currency(self, page: PageWithRetry):

        try:
            await start_on_product_page(page, spoofed_ip=self.simulated_ip)
            await open_cart_and_go_to_cart_page(page)

            # Select a random user from the people.json file and change currency
            checkout_details = random.choice(people)
            await page.select_option('[name="currency_code"]',
                                     value=str(checkout_details['userCurrency']))

            await rum_flush(page)
            log.info("Session completed: open_cart_page_and_change_currency")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)

    @task(1)
    @pw
    async def add_product_to_cart(self, page: PageWithRetry):

        try:
            await start_on_product_page(page, spoofed_ip=self.simulated_ip)

            # Add 1-4 products (possibly different product IDs each time)
            for _ in range(random.choice([1, 2, 3, 4])):
                # We're already on a product page; sometimes change product by direct nav
                pid = random.choice(products)
                await page.goto(f"/product/{pid}", wait_until=PAGE_WAIT_UNTIL)
                await add_random_quantity_and_add_to_cart(page)

            await open_cart_and_go_to_cart_page(page)
            await rum_flush(page)
            log.info("Session completed: add_product_to_cart")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)

    @task(3)
    @pw
    async def add_product_to_cart_and_checkout(self, page: PageWithRetry):
        try:
            page.on("console", lambda msg: print(msg.text) if msg.type in ("warning", "error") else None)
            await page.route('**/*', functools.partial(inject_headers, spoofed_ip=self.simulated_ip))
            await page.goto("/", wait_until="domcontentloaded")

            # Add 1-4 products to the cart
            for i in range(random.choice([1, 2, 3, 4])):
                # Get a random product link and click on it
                product_id = random.choice(products)
                await page.click(f"a[href='/product/{product_id}']")

                # Add a random number of products to the cart
                product_count = random.choice([3, 4, 5, 8, 9, 10])
                await page.select_option('select[data-cy="product-quantity"]', value=str(product_count))

                # add the product to our cart
                await page.click('button:has-text("Add To Cart")')

                # Continue Shopping
                await page.click('button:has-text("Continue Shopping")')

            # Open the Shopping cart flyout
            await page.click('a[data-cy="cart-icon"]')
            # Click the go to shopping cart button
            await page.click('button:has-text("Go to Shopping Cart")')

            # select a random user from the people.json file and checkout
            checkout_details = random.choice(people)
            await page.select_option('select[name="currency_code"]', value=str(checkout_details['userCurrency']))

            await page.locator('input#email').fill(checkout_details['email'])
            await page.locator('input#street_address').fill(checkout_details['address']['streetAddress'])
            await page.locator('input#zip_code').fill(str(checkout_details['address']['zipCode']))
            await page.locator('input#city').fill(checkout_details['address']['city'])
            await page.locator('input#state').fill(checkout_details['address']['state'])
            await page.locator('input#country').fill(checkout_details['address']['country'])
            await page.locator('input#credit_card_number').fill(str(checkout_details['creditCard']['creditCardNumber']))
            await page.select_option('select#credit_card_expiration_month', value=str(checkout_details['creditCard']['creditCardExpirationMonth']))
            await page.select_option('select#credit_card_expiration_year', value=str(checkout_details['creditCard']['creditCardExpirationYear']))
            await page.locator('input#credit_card_cvv').fill(str(checkout_details['creditCard']['creditCardCvv']))

            # Complete the order
            await page.click('button:has-text("Place Order")')
            await page.wait_for_timeout(8000)  # giving the browser time to export the traces
            log.info("Session completed: add_product_to_cart_and_checkout")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)
        

    @task(1)
    @pw
    async def view_product_page(self, page: PageWithRetry):

        try:
            pid = random.choice(["0PUK6V6EV0", "1YMWWN1N4O", "2ZYFJ3GM2N", "66VCHSJNUP"])
            await start_on_product_page(page, product_id=pid, spoofed_ip=self.simulated_ip)
            await rum_flush(page)
            log.info("Session completed: view_product_page")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)
