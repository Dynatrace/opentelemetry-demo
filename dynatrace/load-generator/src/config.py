#!/usr/bin/python
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import random
from pathlib import Path

# ---------------------------------------------------------------------------
# Product catalogue
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Playwright / browser settings
# ---------------------------------------------------------------------------
PAGE_WAIT_UNTIL = os.environ.get("PAGE_WAIT_UNTIL", "load")
if PAGE_WAIT_UNTIL not in ("load", "domcontentloaded", "commit", "networkidle"):
    PAGE_WAIT_UNTIL = "load"

RUM_FLUSH_MS = int(os.environ.get("RUM_FLUSH_MS", "8000"))

# When set to "true" (default), the W3C baggage header "synthetic_request=true" is
# injected into every Playwright request. The frontend SSR uses this flag to route
# browser-side OTLP traces directly to the internal collector instead of the public
# proxy endpoint. Set SYNTHETIC_REQUEST_ENABLED=false on HTTPS deployments where the
# internal collector URL is unreachable from the browser (Mixed Content).
SYNTHETIC_REQUEST_ENABLED = os.environ.get("SYNTHETIC_REQUEST_ENABLED", "true").lower() == "true"

# Pool of public IPs representing real cities across multiple continents.
# Dynatrace resolves geolocation from the IP on RUM beacon requests (/rb_*).
# Each virtual user picks one IP for its entire lifetime so all its sessions
# appear to originate from a consistent location rather than a random per-click one.
simulated_ips = [
    # North America
    "8.8.8.8",  # Google DNS      – Mountain View, CA, US
    "204.79.197.200",  # Bing            – Seattle, WA, US
    "198.41.0.4",  # Cloudflare      – New York, NY, US
    "192.0.2.10",  # TEST-NET        – Chicago, IL, US
    "64.233.160.0",  # Google          – Atlanta, GA, US
    "23.185.0.3",  # Fastly CDN      – Denver, CO, US
    "96.7.128.0",  # Akamai          – Dallas, TX, US
    "208.67.222.222",  # OpenDNS         – San Jose, CA, US
    # Europe
    "185.60.216.35",  # Facebook        – Dublin, IE
    "195.51.195.1",  #                 – Amsterdam, NL
    "81.2.69.160",  #                 – London, GB
    "77.75.77.24",  #                 – Prague, CZ
    "31.13.64.35",  # Facebook        – Frankfurt, DE
    "194.165.16.11",  #                 – Warsaw, PL
    "193.0.14.129",  # RIPE NCC        – Amsterdam, NL
    "212.58.244.20",  # BBC             – London, GB
    # Asia-Pacific
    "203.208.43.1",  # Google Japan    – Tokyo, JP
    "180.76.76.76",  # Baidu DNS       – Beijing, CN
    "202.12.27.33",  # APNIC           – Brisbane, AU
    "103.86.96.100",  #                 – Singapore
    "117.18.232.200",  #                 – Mumbai, IN
    "168.126.63.1",  # KT Corp         – Seoul, KR
    # Latin America
    "200.221.11.100",  #                 – São Paulo, BR
    "201.159.177.1",  #                 – Mexico City, MX
    # Middle East / Africa
    "41.206.26.0",  #                 – Lagos, NG
    "196.202.45.1",  #                 – Nairobi, KE
]

# Headless Chromium advertises "HeadlessChrome" in its User-Agent string, which
# Dynatrace's udger.com-based bot detection classifies as a Robot. Passing
# --user-agent at browser launch replaces it with a real browser UA so sessions
# appear as genuine user traffic in Dynatrace RUM / Digital Experience.
# Each virtual user picks one UA for its entire lifetime so all its sessions
# appear to originate from a consistent browser rather than a random per-click one.
# `label` is used in logs; `ua` is passed to the browser.
user_agents = [
    # Chrome on Windows
    {
        "label": "Chrome/Windows",
        "ua": "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    },
    # Chrome on macOS
    {
        "label": "Chrome/macOS",
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    },
    # Firefox on Windows
    {
        "label": "Firefox/Windows",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    },
    {
        "label": "Firefox/Windows",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    },
    # Firefox on macOS
    {
        "label": "Firefox/macOS",
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    },
    # Safari on macOS
    {
        "label": "Safari/macOS",
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    },
    {
        "label": "Safari/macOS",
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    },
    {
        "label": "Safari/macOS",
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Safari/605.1.15",
    },
    # Edge on Windows
    {
        "label": "Edge/Windows",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    },
    {
        "label": "Edge/Windows",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    },
    # Edge on macOS
    {
        "label": "Edge/macOS",
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.3912.72",
    },
]

# ---------------------------------------------------------------------------
# People / checkout details
# ---------------------------------------------------------------------------
# Each person is loaded from people.json and assigned a fixed simulated IP and
# User-Agent once at load time, so every task run for that person presents a
# consistent location and browser identity throughout the lifetime of the process.
with open(Path(__file__).parent / "people.json") as _people_file:
    people = json.load(_people_file)

for _person in people:
    _person["simulated_ip"] = random.choice(simulated_ips)
    _person["user_agent"] = random.choice(user_agents)

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
