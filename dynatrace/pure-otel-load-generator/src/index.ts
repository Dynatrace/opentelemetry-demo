import {
  createLoadgen,
  createBrowserContextPool,
  createLoggerOptions,
  FunctionProviderWrapper,
} from "@demoability/loadgen-core";
import {
  StatsAggregator,
  StatsRunner,
} from "@demoability/loadgen-core/lib/stats";
import { TIME_UNITS } from "@demoability/loadgen-core/lib/time";
import {
  BROWSER_HEADLESS,
  CONCURRENCY,
  FRONTEND_URL,
  chromiumBaseArgs,
} from "./config";
import { CheckoutVisit } from "./visit";
import { Page } from "puppeteer";

async function main(): Promise<void> {
  console.log(
    `otel-loadgen starting — target: ${FRONTEND_URL.toString()}, concurrency: ${CONCURRENCY}`,
  );

  const visitProvider = new FunctionProviderWrapper(() => new CheckoutVisit());

  const contextPool = createBrowserContextPool({
    name: "otel-loadgen",
    loggerOptions: createLoggerOptions("browser"),
    concurrentBrowsers: 1,
    browserOptions: {
      headless: BROWSER_HEADLESS,
      args: chromiumBaseArgs,
      browser: "chrome",
    },
    browserTimeToLiveMs: 60 * 60 * 1_000,
  });

  const statsAggregator = new StatsAggregator(Date.now());
  const statsRunner = new StatsRunner(
    { unit: TIME_UNITS.SECOND, quantity: 30 },
    { unit: TIME_UNITS.HOUR, quantity: 1 },
    statsAggregator,
    TIME_UNITS.MINUTE,
    [
      { unit: TIME_UNITS.MINUTE, quantity: 5 },
      { unit: TIME_UNITS.HOUR, quantity: 1 },
    ],
    createLoggerOptions("stats"),
  );

  const core = createLoadgen({
    concurrency: CONCURRENCY,
    visitProvider,
    contextPool,
    statsRunner,
    loggerOptions: createLoggerOptions("visit"),
    initialPageSetup: async (page: Page) => {
      await page.setViewport({ width: 1920, height: 1080 });
    },
    // We drive all our own waits and delays inside pageActions.ts /
    // visit.ts — disable the built-in delay helpers so they are no-ops.
    pageActionsConfig: { disableDelay: true },
  });

  // Graceful shutdown on SIGINT / SIGTERM (Docker stop, Ctrl-C).
  let stopping = false;
  async function shutdown(signal: string): Promise<void> {
    if (stopping) return;
    stopping = true;
    console.log(`\nReceived ${signal}, stopping…`);
    await contextPool.stop();
    process.exit(0);
  }
  process.on("SIGINT", () => void shutdown("SIGINT"));
  process.on("SIGTERM", () => void shutdown("SIGTERM"));

  await core.run();
}

main().catch((err: unknown) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
