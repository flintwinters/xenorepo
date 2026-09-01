import createClient from "openapi-fetch";
import type { components, paths } from "../data/openapi";

const api = createClient<paths>();
export type KanbanView = components["schemas"]["KanbanView"];
export type Card = components["schemas"]["CardView"];
export type Column = components["schemas"]["ColumnView"];
export type Comment = components["schemas"]["CommentView"];
export type Attachment = components["schemas"]["AttachmentView"];
export type CardFields = components["schemas"]["CardEdit"];
export type BoardFields = components["schemas"]["BoardEdit"];

function result<T>(data: T | undefined, error: unknown): T {
  if (error) {
    const body = error as { error?: string; detail?: unknown };
    throw new Error(body.error ?? (typeof body.detail === "string" ? body.detail : "Request failed"));
  }
  if (data === undefined) throw new Error("Request returned no data");
  return data;
}

export async function loadBoard(): Promise<KanbanView> {
  const { data, error } = await api.GET("/api/board");
  return result(data, error);
}
export async function editBoard(fields: BoardFields): Promise<void> {
  const { error } = await api.PATCH("/api/board", { body: fields });
  if (error) result(undefined, error);
}
export async function createColumn(name: string, color: string): Promise<void> {
  const { error } = await api.POST("/api/columns", { body: { name, color } });
  if (error) result(undefined, error);
}
export async function editColumn(id: string, name: string, color: string): Promise<void> {
  const { error } = await api.PATCH("/api/columns/{column_id}", {
    params: { path: { column_id: id } }, body: { name, color },
  });
  if (error) result(undefined, error);
}
export async function moveColumn(id: string, position: number): Promise<void> {
  const { error } = await api.PUT("/api/columns/{column_id}/position", {
    params: { path: { column_id: id } }, body: { position },
  });
  if (error) result(undefined, error);
}
export async function createCard(column_id: string, fields: CardFields): Promise<void> {
  const { error } = await api.POST("/api/columns/{column_id}/cards", {
    params: { path: { column_id } }, body: fields,
  });
  if (error) result(undefined, error);
}
export async function editCard(id: string, fields: CardFields): Promise<void> {
  const { error } = await api.PATCH("/api/cards/{card_id}", {
    params: { path: { card_id: id } }, body: fields,
  });
  if (error) result(undefined, error);
}
export async function moveCard(id: string, column_id: string, position: number): Promise<void> {
  const { error } = await api.PUT("/api/cards/{card_id}/position", {
    params: { path: { card_id: id } }, body: { column_id, position },
  });
  if (error) result(undefined, error);
}
export async function addComment(card_id: string, body: string): Promise<void> {
  const { error } = await api.POST("/api/cards/{card_id}/comments", {
    params: { path: { card_id } }, body: { body },
  });
  if (error) result(undefined, error);
}
export async function editComment(id: string, body: string): Promise<void> {
  const { error } = await api.PATCH("/api/comments/{comment_id}", {
    params: { path: { comment_id: id } }, body: { body },
  });
  if (error) result(undefined, error);
}
export async function addLink(card_id: string, title: string, url: string): Promise<void> {
  const { error } = await api.POST("/api/cards/{card_id}/links", {
    params: { path: { card_id } }, body: { title, url },
  });
  if (error) result(undefined, error);
}
export async function addUpload(card_id: string, title: string, file: File): Promise<void> {
  const response = await fetch(`/api/cards/${card_id}/uploads`, { method: "POST", body: file,
    headers: { "Content-Type": file.type || "application/octet-stream",
      "X-Attachment-Title": title, "X-File-Name": file.name } });
  if (!response.ok) throw new Error((await response.json() as { error?: string }).error ?? "Upload failed");
}
export async function editAttachment(id: string, title: string, url?: string): Promise<void> {
  const { error } = await api.PATCH("/api/attachments/{attachment_id}", {
    params: { path: { attachment_id: id } }, body: { title, url: url ?? null },
  });
  if (error) result(undefined, error);
}
export async function setArchived(kind: string, id: string, restore = false): Promise<void> {
  if (restore) {
    const { error } = await api.POST("/api/archive/{kind}/{identity}/restore", {
      params: { path: { kind, identity: id } },
    });
    if (error) result(undefined, error);
    return;
  }
  const { error } = await api.DELETE("/api/archive/{kind}/{identity}", {
    params: { path: { kind, identity: id } },
  });
  if (error) result(undefined, error);
}
