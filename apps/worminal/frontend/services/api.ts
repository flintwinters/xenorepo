import type { Shortcut, WorkspacePayload } from "../types.js";

export class WorminalClient {
  workspace(): Promise<Response> { return fetch("/api/workspace"); }
  saveWorkspace(windows: WorkspacePayload["windows"], shortcuts: Shortcut[]): Promise<Response> {
    return fetch("/api/workspace", { method: "PUT", keepalive: true,
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ windows, shortcuts }) });
  }
  grantAccess(password: string): Promise<Response> {
    return fetch("/api/access", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }) });
  }
  deleteWindow(id: string): Promise<Response> {
    return fetch(`/api/workspace/windows/${id}`, { method: "DELETE" });
  }
  deleteTab(id: string): Promise<Response> {
    return fetch(`/api/workspace/tabs/${id}`, { method: "DELETE" });
  }
}
