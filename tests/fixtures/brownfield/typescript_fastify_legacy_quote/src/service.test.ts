import assert from "node:assert/strict";
import { after, before, test } from "node:test";

import {
  buildApp,
  formatReceipt,
  legacyDiscountHint,
  normalizeCoupon,
  quoteOrder,
} from "./service.js";

const app = buildApp();
let baseUrl = "";

before(async () => {
  baseUrl = await app.listen({ host: "127.0.0.1", port: 0 });
});

after(async () => {
  await app.close();
});

test("real HTTP quote-order path returns the legacy quote result", async () => {
  const response = await fetch(`${baseUrl}/quote-order`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ unit_price_cents: 1250, quantity: 2 }),
  });

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    total_cents: 2500,
    receipt: "Total: 25.00",
  });
});

test("real HTTP quote-order path rejects zero quantity", async () => {
  const response = await fetch(`${baseUrl}/quote-order`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ unit_price_cents: 1250, quantity: 0 }),
  });

  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), {
    error: "quantity must be positive",
  });
});

test("legacy business functions retain their standalone semantics", () => {
  assert.equal(quoteOrder(1250, 2), 2500);
  assert.throws(() => quoteOrder(-1, 2), {
    message: "unit price must not be negative",
  });
  assert.throws(() => quoteOrder(1250, 0), {
    message: "quantity must be positive",
  });
  assert.equal(formatReceipt(2500), "Total: 25.00");
  assert.equal(normalizeCoupon(" save5 "), "SAVE5");
  assert.equal(legacyDiscountHint(" save5 "), 5);
  assert.equal(legacyDiscountHint("unknown"), null);
});
