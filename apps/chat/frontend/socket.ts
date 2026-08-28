import type { ServerEvent } from "./types.js";

export interface ChatTransportCallbacks {
  opened(): void;
  event(event: ServerEvent): void;
  closed(): void;
}

/** Own the reconnecting WebSocket while the component owns product state. */
export class ChatTransport {
  private socket?: WebSocket;
  private retry?: number;

  constructor(private readonly callbacks: ChatTransportCallbacks) {}

  connect(): void {
    window.clearTimeout(this.retry);
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    this.socket = new WebSocket(`${protocol}://${location.host}/ws`);
    this.socket.onopen = () => this.callbacks.opened();
    this.socket.onmessage = ({ data }) => this.callbacks.event(JSON.parse(data) as ServerEvent);
    this.socket.onclose = () => {
      this.callbacks.closed();
      this.retry = window.setTimeout(() => this.connect(), 1500);
    };
    this.socket.onerror = () => this.socket?.close();
  }

  send(payload: object): boolean {
    if (this.socket?.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify(payload));
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
