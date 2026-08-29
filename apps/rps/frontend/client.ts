import createClient from "openapi-fetch";
import type { components, paths } from "../data/openapi";

const api = createClient<paths>();
export type SessionPlayer = components["schemas"]["PlayerState"];

function result<T>(data: T | undefined, error: unknown): T {
  if (error) {
    const body = error as { error?: string; detail?: unknown };
    const message = body.error ?? (typeof body.detail === "string" ? body.detail : "REQUEST FAILED");
    const failure = new Error(message) as Error & { status?: number };
    const status = (error as { status?: number }).status;
    if (status !== undefined) failure.status = status;
    throw failure;
  }
  if (data === undefined) throw new Error("REQUEST RETURNED NO DATA");
  return data;
}

export async function loadSession(): Promise<SessionPlayer> {
  const { data, error, response } = await api.GET("/api/session");
  const status = response.status;
  if (error) (error as { status?: number }).status = status;
  return result(data, error);
}

export async function renameSession(nickname: string): Promise<SessionPlayer> {
  const { data, error, response } = await api.PATCH("/api/session", { body: { nickname } });
  if (error) (error as { status?: number }).status = response.status;
  return result(data, error);
}
