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
