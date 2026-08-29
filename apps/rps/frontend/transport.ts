import { parseServerEvent, type ServerEvent } from "./types.js";

export interface ArenaTransportCallbacks {
  opened(): void;
  event(event: ServerEvent): void;
  closed(): void;
}

/** Own the reconnecting WebSocket while the component owns arena state. */
export class ArenaTransport {
  private socket?: WebSocket;
  private retry?: number;

  constructor(private readonly callbacks: ArenaTransportCallbacks) {}

  connect(): void {
    window.clearTimeout(this.retry);
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    this.socket = new WebSocket(`${protocol}://${location.host}/ws`);
    this.socket.onopen = () => this.callbacks.opened();
    this.socket.onmessage = ({ data }) => {
      let event: ServerEvent | undefined;
      try {
        event = typeof data === "string" ? parseServerEvent(JSON.parse(data) as unknown) : undefined;
      } catch {
        event = undefined;
      }
      this.callbacks.event(event ?? { type: "error", message: "INVALID SERVER MESSAGE" });
    };
    this.socket.onclose = () => {
      this.callbacks.closed();
      this.retry = window.setTimeout(() => this.connect(), 2000);
    };
    this.socket.onerror = () => this.socket?.close();
  }

  send(type: string, data: object = {}): boolean {
    if (this.socket?.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify({ type, client_id: crypto.randomUUID(), ...data }));
    return true;
  }

  disconnect(): void {
    window.clearTimeout(this.retry);
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
    }
  }
}
