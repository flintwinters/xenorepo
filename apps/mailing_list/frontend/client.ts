import createClient from "openapi-fetch";
import type { paths } from "../data/openapi";

const client = createClient<paths>();

export interface ErrorEnvelope {
  error: string;
}

export function errorMessage(value: unknown): string {
  if (typeof value !== "object" || value === null || !("error" in value)) return "CHECKOUT FAILED";
  return typeof value.error === "string" ? value.error : "CHECKOUT FAILED";
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
