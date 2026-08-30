import createClient from "openapi-fetch";
import type { paths } from "../data/openapi";

const client = createClient<paths>();

export interface ErrorEnvelope {
  error: string;
}

function record(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null ? value as Record<string, unknown> : undefined;
}

function validationMessage(value: unknown): string | undefined {
  if (!Array.isArray(value)) return undefined;
  for (const item of value) {
    const message = record(item)?.msg;
    if (typeof message === "string") return message;
  }
  return undefined;
}

export function errorMessage(value: unknown): string {
  const body = record(value);
  if (!body) return "Unable to reach checkout. Please try again.";
  if (typeof body.error === "string") return body.error;
  if (typeof body.detail === "string") return body.detail;
  const message = validationMessage(body.detail);
  if (message) return message;
  return "Unable to start checkout. Please try again.";
}

export async function offering() {
  const result = await client.GET("/api/offering");
  if (!result.data) throw new Error(errorMessage(result.error));
  return result.data;
}

export async function checkout(email: string) {
  const result = await client.POST("/api/checkouts", { body: { email } });
  if (!result.data) throw new Error(errorMessage(result.error));
  return result.data;
}

export async function checkoutStatus(checkoutId: string) {
  const result = await client.GET("/api/checkouts/{checkout_id}", {
    params: { path: { checkout_id: checkoutId } },
  });
  if (!result.data) throw new Error(errorMessage(result.error));
  return result.data;
}

export async function settleSandbox(checkoutId: string, state: "paid" | "cancelled") {
  const result = await client.POST("/api/sandbox/checkouts/{checkout_id}/{state}", {
    params: { path: { checkout_id: checkoutId, state } },
  });
  if (!result.data) throw new Error(errorMessage(result.error));
  return result.data;
}
