import { CssSelector, XpathSelector } from "@demoability/loadgen-core";

/**
 * Selectors for the OTel demo frontend.
 *
 * Convention (mirrors easytrade loadgen):
 *   - Use CssSelector for elements that have stable data-cy attributes or ids.
 *   - Use XpathSelector for elements identified purely by text when no stable
 *     attribute is available (text()= for exact match, contains() for partial).
 *
 * All selectors go through page.waitForSelector({ visible: true }) internally,
 * so they wait for the element to be in the DOM and visible before interacting.
 */
export const selectors = {
  // -------------------------------------------------------------------------
  // Product listing page
  // -------------------------------------------------------------------------
  productCard: new CssSelector("product-card", '[data-cy="product-card"]'),
  addToCart: new CssSelector("add-to-cart", '[data-cy="product-add-to-cart"]'),
  productQuantity: new CssSelector(
    "product-quantity",
    'select[data-cy="product-quantity"]',
  ),

  // -------------------------------------------------------------------------
  // Cart / checkout page
  // -------------------------------------------------------------------------
  continueShopping: new XpathSelector(
    "continue-shopping",
    '//button[text()="Continue Shopping"]',
  ),
  placeOrder: new CssSelector(
    "place-order",
    '[data-cy="checkout-place-order"]',
  ),

  // Checkout form fields
  currencySelect: new CssSelector(
    "currency-select",
    'select[name="currency_code"]',
  ),
  emailInput: new CssSelector("email-input", "input#email"),
  streetAddress: new CssSelector("street-address", "input#street_address"),
  zipCode: new CssSelector("zip-code", "input#zip_code"),
  city: new CssSelector("city-input", "input#city"),
  state: new CssSelector("state-input", "input#state"),
  country: new CssSelector("country-input", "input#country"),
  creditCardNumber: new CssSelector(
    "credit-card-number",
    "input#credit_card_number",
  ),
  expirationMonth: new CssSelector(
    "expiration-month",
    "select#credit_card_expiration_month",
  ),
  expirationYear: new CssSelector(
    "expiration-year",
    "select#credit_card_expiration_year",
  ),
  creditCardCvv: new CssSelector("credit-card-cvv", "input#credit_card_cvv"),
};
