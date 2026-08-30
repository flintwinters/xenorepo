import createClient from "openapi-fetch";
import type { paths } from "../data/openapi";

const client = createClient<paths>();

export interface ErrorEnvelope {
  error: string;
}

export function errorMessage(value: unknown): string {
  if (typeof value !== "object" || value === null) return "Unable to reach checkout. Please try again.";
  if ("error" in value && typeof value.error === "string") return value.error;
  if ("detail" in value && typeof value.detail === "string") return value.detail;
  if ("detail" in value && Array.isArray(value.detail)) {
    const message = value.detail.find((item) => typeof item === "object" && item !== null
      && "msg" in item && typeof item.msg === "string");
    if (message && "msg" in message) return message.msg as string;
  }
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

export async function settleSandbox(checkoutId: string, state: "paid" | "cancelled") {
  const result = await client.POST("/api/sandbox/checkouts/{checkout_id}/{state}", {
    params: { path: { checkout_id: checkoutId, state } },
  });
  if (!result.data) throw new Error(errorMessage(result.error));
  return result.data;
}
