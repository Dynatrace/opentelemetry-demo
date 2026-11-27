import crypto from "crypto";
import { Logger } from "winston";
import {
  IVisit,
  IPageActions,
  PageActions,
  addContext,
  delay,
} from "@demoability/loadgen-core";
import {
  FRONTEND_URL,
  PAGE_WAIT_UNTIL,
  SYNTHETIC_REQUEST_ENABLED,
  Person,
  people,
} from "./config";
import { waitForBanner, orderProduct, completeCheckout } from "./pageActions";
import { selectors } from "./selectors";

function randomPerson(): Person {
  return people[Math.floor(Math.random() * people.length)];
}

/**
 * A single browse-and-checkout task.
 * Mirrors the Python `WebsiteBrowserUser.browse_and_checkout` task.
 *
 * A new instance is created for every task run via FunctionProviderWrapper,
 * so the person is randomised per visit (matching Python's tracked_task
 * decorator which picks a person per call).
 */
export class CheckoutVisit implements IVisit {
  private readonly person: Person;
  private taskId: string;
  private startTime: number = 0;

  constructor() {
    this.person = randomPerson();
    this.taskId = crypto.randomBytes(4).toString("hex");
  }

  getName(): string {
    return "browse_and_checkout";
  }

  /**
   * Called by VisitWorker before run(). Configures the fresh Puppeteer page
   * with persona-specific UA, baggage header, navigator.userAgent override,
   * and an x-forwarded-for injector on RUM beacon requests.
   */
  async setup(pageActions: IPageActions, logger: Logger): Promise<void> {
    this.startTime = Date.now();
    addContext(logger, {
      taskId: this.taskId,
      simulatedIp: this.person.simulatedIp,
      userAgent: this.person.userAgent.label,
    });

    logger.info(
      `[${this.taskId}] Task started: ip=[${this.person.simulatedIp}] ua=[${this.person.userAgent.label}]`,
    );

    await pageActions.setupPage(async (page) => {
      const person = this.person;
      await page.setUserAgent({ userAgent: person.userAgent.ua });

      // Optional W3C baggage header so the frontend SSR can identify
      // synthetic browser traffic and route RUM beacons to the internal
      // collector.
      if (SYNTHETIC_REQUEST_ENABLED) {
        await page.setExtraHTTPHeaders({
          baggage: "synthetic_request=true",
        });
      }

      // the cdn rejects the requests with the header, so setting it on all
      // requests results in no monitoring, there are other workarounds,
      // but this allows for both monitoring and different locations picked up
      // by dynatrace
      await page.setRequestInterception(true);
      page.on("request", (request) => {
        if (request.url().includes("js-cdn.dynatrace.com")) {
          void request.continue();
        } else {
          void request.continue({
            headers: {
              ...request.headers(),
              "x-forwarded-for": person.simulatedIp,
            },
          });
        }
      });
    });
  }

  /**
   * Executes the browse-and-checkout flow. Mirrors Python's
   * `browse_and_checkout` task body.
   */
  async run(pageActions: IPageActions, logger: Logger): Promise<void> {
    // Raw Page is still needed for page.goto() and waitForFunction-based
    // banner/product-card waits, which are not part of IPageActions.
    const page = (pageActions as PageActions).page;

    try {
      // Navigate to homepage and wait for the banner LCP to trigger.
      await page.goto(FRONTEND_URL.toString(), {
        waitUntil: PAGE_WAIT_UNTIL,
        timeout: 60_000,
      });
      await waitForBanner(page);

      // Pick a product and add it to cart.
      await orderProduct(pageActions, logger);

      // Continue shopping — uses XpathSelector which calls
      // waitForSelector({ visible: true }) before clicking, so it
      // handles both timing and selector reliability in one call.
      await pageActions.navigate(selectors.continueShopping);
      await waitForBanner(page);

      // Pick a second product and add it to cart.
      await orderProduct(pageActions, logger);

      // Fill checkout form and place order.
      await completeCheckout(pageActions, this.person, logger);

      await delay(2_000);

      const duration = ((Date.now() - this.startTime) / 1_000).toFixed(2);
      logger.info(
        `[${this.taskId}] Task completed: ip=[${this.person.simulatedIp}] ua=[${this.person.userAgent.label}] duration=[${duration}s]`,
      );
    } finally {
      addContext(logger, {
        taskId: undefined,
        simulatedIp: undefined,
        userAgent: undefined,
      });
    }
  }
}
