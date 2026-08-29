import createClient from "openapi-fetch";
import type { components, paths } from "../data/openapi";

const api = createClient<paths>();
export type CalendarEvent = components["schemas"]["Event"];
export type CalendarView = components["schemas"]["CalendarView"];
export type EventCreate = components["schemas"]["EventCreate"];
export type EventUpdate = components["schemas"]["EventUpdate"];

function result<T>(data: T | undefined, error: unknown): T {
  if (error) {
    const body = error as { error?: string; detail?: unknown };
    throw new Error(body.error ?? (typeof body.detail === "string" ? body.detail : "Request failed"));
  }
  if (data === undefined) throw new Error("Request returned no data");
  return data;
}

export async function loadCalendar(start: string, end: string): Promise<CalendarView> {
  const { data, error } = await api.GET("/api/calendar", { params: { query: { start, end } } });
  return result(data, error);
}
export async function initializeTimeZone(time_zone: string): Promise<void> {
  const { error } = await api.PUT("/api/settings/time-zone", { body: { time_zone } });
  if (error) result(undefined, error);
}
export async function createEvent(body: EventCreate): Promise<CalendarEvent> {
  const { data, error } = await api.POST("/api/events", { body });
  return result(data, error);
}
export async function updateEvent(eventId: string, body: EventUpdate): Promise<CalendarEvent> {
  const { data, error } = await api.PATCH("/api/events/{event_id}", {
    params: { path: { event_id: eventId } },
    body,
  });
  return result(data, error);
}
export async function deleteEvent(eventId: string): Promise<void> {
  const { error } = await api.DELETE("/api/events/{event_id}", { params: { path: { event_id: eventId } } });
  if (error) result(undefined, error);
}
