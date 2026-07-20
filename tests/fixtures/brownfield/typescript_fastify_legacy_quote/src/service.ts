import Fastify, { type FastifyInstance } from "fastify";

type QuoteOrderBody = {
  readonly unit_price_cents?: unknown;
  readonly quantity?: unknown;
};

function requireInteger(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isInteger(value)) {
    throw new Error(`${field} must be an integer`);
  }
  return value;
}

export function quoteOrder(
  unitPriceCents: number,
  quantity: number,
): number {
  if (unitPriceCents < 0) {
    throw new Error("unit price must not be negative");
  }
  if (quantity <= 0) {
    throw new Error("quantity must be positive");
  }
  return unitPriceCents * quantity;
}

export function formatReceipt(totalCents: number): string {
  return `Total: ${(totalCents / 100).toFixed(2)}`;
}

export function normalizeCoupon(code: string): string {
  return code.trim().toUpperCase();
}

export function legacyDiscountHint(code: string): number | null {
  return normalizeCoupon(code) === "SAVE5" ? 5 : null;
}

export function buildApp(): FastifyInstance {
  const app = Fastify({ logger: false });

  app.post<{ Body: QuoteOrderBody }>("/quote-order", async (request, reply) => {
    try {
      const unitPriceCents = requireInteger(
        request.body.unit_price_cents,
        "unit price",
      );
      const quantity = requireInteger(request.body.quantity, "quantity");
      const totalCents = quoteOrder(unitPriceCents, quantity);
      return reply.status(200).send({
        total_cents: totalCents,
        receipt: formatReceipt(totalCents),
      });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "invalid request";
      return reply.status(400).send({ error: message });
    }
  });

  return app;
}
