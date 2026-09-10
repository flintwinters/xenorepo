import createClient from "openapi-fetch";
import type { components, paths } from "../data/openapi";

const api = createClient<paths>();
export type Contact = components["schemas"]["Contact"];
export type ContactFields = components["schemas"]["ContactCreate"];

function checked<T>(data: T | undefined, error: unknown): T {
  if (error) {
    const body = error as { error?: string; detail?: string | Array<{ msg?: string }> };
    throw new Error(body.error ?? (typeof body.detail === "string" ? body.detail :
      body.detail?.[0]?.msg ?? "Request failed"));
  }
  if (data === undefined) throw new Error("Request returned no data");
  return data;
}
export async function saveContact(id: string | null, body: ContactFields): Promise<Contact> {
  if (id) { const { data, error } = await api.PUT("/api/contacts/{contact_id}", {
    params: { path: { contact_id: id } }, body }); return checked(data, error); }
  const { data, error } = await api.POST("/api/contacts", { body }); return checked(data, error);
}
export async function deleteContact(id: string): Promise<void> {
  const { error } = await api.DELETE("/api/contacts/{contact_id}", { params: { path: { contact_id: id } } });
  if (error) checked(undefined, error);
}
