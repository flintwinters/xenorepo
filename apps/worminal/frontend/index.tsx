import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { render } from "preact";
import { useEffect, useRef, useState } from "preact/hooks";
import { ConsolePane, ConsoleShell, ConsoleWorkspace, StatusRail, UtilityRail } from "monoui";
import "./styles.css";

type ConnectionState = "CONNECTING" | "CONNECTED" | "EXITED" | "FAILED";
type Frame = { x: number; y: number; width: number; height: number };
type Gesture = { id: number; startX: number; startY: number; frame: Frame };

const MIN_WIDTH = 320, MIN_HEIGHT = 240;

function initialFrame(): Frame {
  return { x: 32, y: 28, width: Math.max(MIN_WIDTH, Math.min(900, window.innerWidth - 64)),
    height: Math.max(MIN_HEIGHT, Math.min(620, window.innerHeight - 112)) };
}

function contain(frame: Frame): Frame {
  const workspaceHeight = Math.max(MIN_HEIGHT, window.innerHeight - 112);
  const width = Math.min(frame.width, window.innerWidth), height = Math.min(frame.height, workspaceHeight);
  return { width, height, x: Math.max(0, Math.min(frame.x, window.innerWidth - width)),
    y: Math.max(0, Math.min(frame.y, workspaceHeight - height)) };
}

function socketUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/terminal`;
}

function Application() {
  const host = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<ConnectionState>("CONNECTING");
  const [frame, setFrame] = useState<Frame>(initialFrame);
  const drag = useRef<Gesture | null>(null), sizing = useRef<Gesture | null>(null);
  const startGesture = (target: EventTarget | null, event: PointerEvent,
    holder: { current: Gesture | null }): void => {
    holder.current = { id: event.pointerId, startX: event.clientX, startY: event.clientY, frame };
    (target as HTMLElement).setPointerCapture(event.pointerId);
  };
  const moveDrag = (event: PointerEvent): void => {
    const gesture = drag.current;
    if (gesture?.id !== event.pointerId) return;
    setFrame(contain({ ...gesture.frame, x: gesture.frame.x + event.clientX - gesture.startX,
      y: gesture.frame.y + event.clientY - gesture.startY }));
  };
  const moveResize = (event: PointerEvent): void => {
    const gesture = sizing.current;
    if (gesture?.id !== event.pointerId) return;
    setFrame(contain({ ...gesture.frame,
      width: Math.max(MIN_WIDTH, gesture.frame.width + event.clientX - gesture.startX),
      height: Math.max(MIN_HEIGHT, gesture.frame.height + event.clientY - gesture.startY) }));
  };
  const nudge = (event: KeyboardEvent): void => {
    const movement: Record<string, [number, number]> = { ArrowLeft: [-10, 0], ArrowRight: [10, 0],
      ArrowUp: [0, -10], ArrowDown: [0, 10] };
    const delta = movement[event.key];
    if (!delta) return;
    event.preventDefault(); const [x, y] = delta;
    setFrame((current) => contain({ ...current, x: current.x + x, y: current.y + y }));
  };
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
  useEffect(() => {
    const keepVisible = () => setFrame((current) => contain(current));
    window.addEventListener("resize", keepVisible);
    return () => window.removeEventListener("resize", keepVisible);
  }, []);
  const header = <UtilityRail><strong>WORMINAL</strong><span>LOCAL SHELL</span></UtilityRail>;
  const footer = <StatusRail><span role="status">{state}</span><span>EPHEMERAL SESSION</span></StatusRail>;
  return <ConsoleShell class="worminal-shell" header={header} footer={footer}>
    <ConsoleWorkspace class="workspace"><ConsolePane title="TERMINAL" tone="green"
      class="terminal-window" style={{ left: frame.x, top: frame.y, width: frame.width,
        height: frame.height }} chromeProps={{ role: "button", tabIndex: 0,
        "aria-label": "Move terminal window", onKeyDown: nudge,
        onPointerDown: (event) => startGesture(event.currentTarget, event, drag),
        onPointerMove: moveDrag, onPointerUp: () => { drag.current = null; } }}>
      <div class="terminal-host" ref={host} />
      <div class="resize-handle" role="separator" tabIndex={0} aria-label="Resize terminal window"
        onPointerDown={(event) => startGesture(event.currentTarget, event, sizing)}
        onPointerMove={moveResize} onPointerUp={() => { sizing.current = null; }} />
    </ConsolePane></ConsoleWorkspace>
  </ConsoleShell>;
}

export function mount(root: HTMLElement): void { render(<Application />, root); }
