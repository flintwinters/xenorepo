export interface ChatMessage {
  id: number;
  author: string;
  body: string;
  created_at: string;
}

export type ServerEvent =
  | { type: "history"; messages: ChatMessage[] }
  | { type: "message"; message: ChatMessage }
  | { type: "presence"; count: number }
  | { type: "error"; message: string };

export type ConnectionState = "connecting" | "online" | "offline";

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function message(value: unknown): value is ChatMessage {
  return (
    record(value) &&
    typeof value.id === "number" &&
    Number.isInteger(value.id) &&
    typeof value.author === "string" &&
    typeof value.body === "string" &&
    typeof value.created_at === "string"
  );
}

type EventRecord = Record<string, unknown>;
type EventParser = (value: EventRecord) => ServerEvent | undefined;

const historyEvent: EventParser = (value) => {
  if (!Array.isArray(value.messages) || !value.messages.every(message)) return undefined;
  return { type: "history", messages: value.messages };
};

const messageEvent: EventParser = (value) =>
  message(value.message) ? { type: "message", message: value.message } : undefined;

const presenceEvent: EventParser = (value) => {
  if (typeof value.count !== "number" || !Number.isInteger(value.count) || value.count < 0) return undefined;
  return { type: "presence", count: value.count };
};

const errorEvent: EventParser = (value) =>
  typeof value.message === "string" ? { type: "error", message: value.message } : undefined;

const eventParsers: Record<string, EventParser> = {
  history: historyEvent,
  message: messageEvent,
  presence: presenceEvent,
  error: errorEvent,
};

/** Validate the app-owned realtime union at the untrusted WebSocket boundary. */
export function parseServerEvent(value: unknown): ServerEvent | undefined {
  if (!record(value) || typeof value.type !== "string") return undefined;
  return eventParsers[value.type]?.(value);
}
