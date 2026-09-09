import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { render } from "preact";
import { useEffect, useRef, useState } from "preact/hooks";
import { ConsolePane, ConsoleShell, ConsoleWorkspace, StatusRail, UtilityRail } from "monoui";
import "./styles.css";

type ConnectionState = "CONNECTING" | "CONNECTED" | "EXITED" | "FAILED";

function socketUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/terminal`;
}

function Application() {
  const host = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<ConnectionState>("CONNECTING");
  useEffect(() => {
    if (!host.current) return;
    const terminal = new Terminal({ cursorBlink: true, convertEol: false,
      fontFamily: '"JetBrains Mono", "Cascadia Mono", monospace', fontSize: 14,
      theme: { background: "#1d2021", foreground: "#ebdbb2", cursor: "#fabd2f" } });
    const fit = new FitAddon();
    terminal.loadAddon(fit); terminal.open(host.current); fit.fit();
    const socket = new WebSocket(socketUrl()); socket.binaryType = "arraybuffer";
    const resize = () => { fit.fit(); if (socket.readyState === WebSocket.OPEN) socket.send(
      JSON.stringify({ type: "resize", rows: terminal.rows, columns: terminal.cols })); };
    socket.addEventListener("open", () => { setState("CONNECTED"); resize(); terminal.focus(); });
    socket.addEventListener("message", (event) => terminal.write(
      event.data instanceof ArrayBuffer ? new Uint8Array(event.data) : event.data));
    socket.addEventListener("close", () => setState("EXITED"));
    socket.addEventListener("error", () => setState("FAILED"));
    const input = terminal.onData((data) => { if (socket.readyState === WebSocket.OPEN) socket.send(
      JSON.stringify({ type: "input", data })); });
    const observer = new ResizeObserver(resize); observer.observe(host.current);
    return () => { observer.disconnect(); input.dispose(); socket.close(); terminal.dispose(); };
  }, []);
  const header = <UtilityRail><strong>WORMINAL</strong><span>LOCAL SHELL</span></UtilityRail>;
  const footer = <StatusRail><span role="status">{state}</span><span>EPHEMERAL SESSION</span></StatusRail>;
  return <ConsoleShell class="worminal-shell" header={header} footer={footer}>
    <ConsoleWorkspace class="workspace"><ConsolePane title="TERMINAL" tone="green">
      <div class="terminal-host" ref={host} />
    </ConsolePane></ConsoleWorkspace>
  </ConsoleShell>;
}

export function mount(root: HTMLElement): void { render(<Application />, root); }
