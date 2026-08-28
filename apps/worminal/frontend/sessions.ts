import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";

export interface TerminalSession {
  socket: WebSocket;
  terminal: Terminal;
  fit: FitAddon;
  resize?: ResizeObserver;
}

/** Owns terminal resources so teardown remains complete and idempotent. */
export class SessionRegistry {
  readonly sessions = new Map<string, TerminalSession>();
  has(id: string): boolean {
    return this.sessions.has(id);
  }
  get(id: string): TerminalSession | undefined {
    return this.sessions.get(id);
  }
  set(id: string, session: TerminalSession): void {
    this.sessions.set(id, session);
  }
  keys(): IterableIterator<string> {
    return this.sessions.keys();
  }
  destroy(id: string): void {
    const session = this.sessions.get(id);
    if (!session) return;
    session.resize?.disconnect();
    session.socket.close();
    session.terminal.dispose();
    this.sessions.delete(id);
  }
}
