import fs from "fs";
import path from "path";
import { EnvConfig } from "@demoability/loadgen-core";
import type { PuppeteerLifeCycleEvent } from "puppeteer";

// ---------------------------------------------------------------------------
// Browser / page settings
// ---------------------------------------------------------------------------

const PAGE_WAIT_UNTIL_VALUES = [
  "load",
  "domcontentloaded",
  "networkidle0",
  "networkidle2",
] as const satisfies readonly PuppeteerLifeCycleEvent[];

// Mirrors Python's PAGE_WAIT_UNTIL env var; maps Playwright's "networkidle"
// to Puppeteer's "networkidle0".
function resolvePageWaitUntil(
  raw: string | undefined,
): PuppeteerLifeCycleEvent {
  if (raw === "networkidle") return "networkidle0";
  if ((PAGE_WAIT_UNTIL_VALUES as readonly string[]).includes(raw ?? "")) {
    return raw as PuppeteerLifeCycleEvent;
  }
  return "load";
}

export const PAGE_WAIT_UNTIL: PuppeteerLifeCycleEvent = resolvePageWaitUntil(
  process.env["PAGE_WAIT_UNTIL"],
);

export const BROWSER_HEADLESS: boolean =
  (process.env["BROWSER_HEADLESS"] ?? "true").toLowerCase() !== "false";

export const SYNTHETIC_REQUEST_ENABLED: boolean =
  (process.env["SYNTHETIC_REQUEST_ENABLED"] ?? "false").toLowerCase() === "true";

export const FRONTEND_URL: URL = EnvConfig.ensureUrl(
  "FRONTEND_URL",
  new URL("http://frontend"),
);

export const CONCURRENCY: number = EnvConfig.ensureNumber("CONCURRENCY", 2);

export const ACTION_DURATION_MS: number = EnvConfig.ensureNumber(
  "ACTION_DURATION_MS",
  100,
);

// ---------------------------------------------------------------------------
// Simulated IPs — same pool as the Python source
// ---------------------------------------------------------------------------
export const simulatedIps: string[] = [
  // North America
  "8.8.8.8",
  "204.79.197.200",
  "198.41.0.4",
  "192.0.2.10",
  "64.233.160.0",
  "23.185.0.3",
  "96.7.128.0",
  "208.67.222.222",
  // Europe
  "185.60.216.35",
  "195.51.195.1",
  "81.2.69.160",
  "77.75.77.24",
  "31.13.64.35",
  "194.165.16.11",
  "193.0.14.129",
  "212.58.244.20",
  // Asia-Pacific
  "203.208.43.1",
  "180.76.76.76",
  "202.12.27.33",
  "103.86.96.100",
  "117.18.232.200",
  "168.126.63.1",
  // Latin America
  "200.221.11.100",
  "201.159.177.1",
  // Middle East / Africa
  "41.206.26.0",
  "196.202.45.1",
];

// ---------------------------------------------------------------------------
// User-Agent strings — same list as the Python source
// ---------------------------------------------------------------------------
export interface UserAgent {
  label: string;
  ua: string;
}

export const userAgents: UserAgent[] = [
  {
    label: "Chrome/Windows",
    ua: "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
  },
  {
    label: "Chrome/macOS",
    ua: "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
  },
  {
    label: "Firefox/Windows",
    ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
  },
  {
    label: "Firefox/Windows",
    ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
  },
  {
    label: "Firefox/macOS",
    ua: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
  },
  {
    label: "Safari/macOS",
    ua: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
  },
  {
    label: "Safari/macOS",
    ua: "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
  },
  {
    label: "Safari/macOS",
    ua: "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Safari/605.1.15",
  },
  {
    label: "Edge/Windows",
    ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
  },
  {
    label: "Edge/Windows",
    ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
  },
  {
    label: "Edge/macOS",
    ua: "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.3912.72",
  },
];

// ---------------------------------------------------------------------------
// Chromium launch args — same flags as the Python source (+--no-sandbox for
// container compatibility)
// ---------------------------------------------------------------------------
export const chromiumBaseArgs: string[] = [
  "--no-sandbox",
  "--disable-setuid-sandbox",
  "--disable-gpu",
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
  "--deny-permission-prompts",
  "--disable-logging",
  "--disable-permissions-api",
  "--ignore-certificate-errors",
  "--proxy-server='direct://'",
  "--proxy-bypass-list=*",
  "--no-first-run",
  "--disable-audio-output",
  "--disable-canvas-aa",
  "--disable-dev-shm-usage",
];

// ---------------------------------------------------------------------------
// People — loaded from people.json, enriched at startup with a fixed
// simulated IP and User-Agent (matches Python: one identity per process lifetime)
// ---------------------------------------------------------------------------
export interface PersonAddress {
  streetAddress: string;
  zipCode: string;
  city: string;
  state: string;
  country: string;
}

export interface PersonCreditCard {
  creditCardNumber: string;
  creditCardExpirationMonth: number;
  creditCardExpirationYear: number;
  creditCardCvv: number;
}

export interface Person {
  email: string;
  address: PersonAddress;
  userCurrency: string;
  creditCard: PersonCreditCard;
  simulatedIp: string;
  userAgent: UserAgent;
}

function randomChoice<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function loadPeople(): Person[] {
  const raw = JSON.parse(
    fs.readFileSync(path.join(__dirname, "people.json"), "utf-8"),
  ) as Omit<Person, "simulatedIp" | "userAgent">[];

  return raw.map((p) => ({
    ...p,
    simulatedIp: randomChoice(simulatedIps),
    userAgent: randomChoice(userAgents),
  }));
}

export const people: Person[] = loadPeople();
