import createClient from "openapi-fetch";
import type { components, paths } from "../data/openapi";

const api = createClient<paths>();
export type Board = components["schemas"]["Board"];
export type Card = components["schemas"]["Card"];
export type CardCreate = components["schemas"]["CardCreate"];
export type CardNote = components["schemas"]["CardNote"];
export type CardUpdate = components["schemas"]["CardUpdate"];
export type Column = components["schemas"]["Column"];

function result<T>(data: T | undefined, error: unknown): T {
  if (error) {
    const body = error as { error?: string; detail?: unknown };
    throw new Error(body.error ?? (typeof body.detail === "string" ? body.detail : "Request failed"));
  }
  if (data === undefined) throw new Error("Request returned no data");
  return data;
}

export async function loadBoard(): Promise<Board> {
  const { data, error } = await api.GET("/api/board");
  return result(data, error);
}
export async function createCard(body: CardCreate): Promise<Card> {
  const { data, error } = await api.POST("/api/cards", { body });
  return result(data, error);
}
export async function updateCard(cardId: string, body: CardUpdate): Promise<Card> {
  const { data, error } = await api.PATCH("/api/cards/{card_id}", {
    params: { path: { card_id: cardId } }, body,
  });
  return result(data, error);
}
export async function deleteCard(cardId: string): Promise<void> {
  const { error } = await api.DELETE("/api/cards/{card_id}", {
    params: { path: { card_id: cardId } },
  });
  if (error) result(undefined, error);
}
export async function appendCardNote(cardId: string, body: string): Promise<CardNote> {
  const { data, error } = await api.POST("/api/cards/{card_id}/notes", {
    params: { path: { card_id: cardId } }, body: { body },
  });
  return result(data, error);
}
export async function changeHistory(path: "undo" | "redo"): Promise<Board> {
  const response = path === "undo" ? await api.POST("/api/undo") : await api.POST("/api/redo");
  return result(response.data, response.error);
}
