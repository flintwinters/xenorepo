/** OpenAPI-derived HTTP boundary for WIRE/98. */
import createClient from "openapi-fetch";
import type { components, paths } from "../data/openapi";

const client = createClient<paths>();
export type Credentials = components["schemas"]["Credentials"];
export type Post = components["schemas"]["PostView"];
export type Session = components["schemas"]["SessionView"];

function value<T>(data: T | undefined, error: unknown): T {
  if (error) {
    const body = error as { error?: string; detail?: unknown };
    throw new Error(body.error ?? (typeof body.detail === "string" ? body.detail : "Request failed."));
  }
  if (data === undefined) throw new Error("Invalid server response.");
  return data;
}

export async function session(): Promise<Session> {
  const result = await client.GET("/api/session");
  return value(result.data, result.error);
}

export async function authenticate(mode: "login" | "register", body: Credentials): Promise<Session> {
  const result = mode === "login"
    ? await client.POST("/api/sessions", { body })
    : await client.POST("/api/accounts", { body });
  return value(result.data, result.error);
}

export async function logout(): Promise<Session> {
  const result = await client.DELETE("/api/session");
  return value(result.data, result.error);
}

export async function posts(before?: number): Promise<Post[]> {
  const result = await client.GET("/api/posts", {
    params: { query: { limit: "100", ...(before === undefined ? {} : { before: String(before) }) } },
  });
  return value(result.data, result.error);
}

export async function publish(body: string): Promise<Post> {
  const result = await client.POST("/api/posts", { body: { body } });
  return value(result.data, result.error);
}

export async function setLike(post: Post): Promise<Post> {
  const params = { path: { post_id: post.id } };
  const result = post.liked_by_me
    ? await client.DELETE("/api/posts/{post_id}/like", { params })
    : await client.PUT("/api/posts/{post_id}/like", { params });
  return value(result.data, result.error);
}
