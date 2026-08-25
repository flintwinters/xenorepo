export type Phase = "connecting" | "ready" | "closed" | "failed";

export interface TabState {
  id: string;
  title: string;
  position: number;
  phase: Phase;
}

export interface WindowState {
  id: string;
  title: string;
  x: number;
  y: number;
  width: number;
  height: number;
  z: number;
  minimized: boolean;
  maximized: boolean;
  active_tab_id: string;
  tabs: TabState[];
}

export interface Shortcut {
  action: "new-shell";
  key: string;
  control: boolean;
  alt: boolean;
  shift: boolean;
  meta: boolean;
}

export interface WorkspacePayload {
  windows: Array<Omit<WindowState, "tabs"> & { tabs: Omit<TabState, "phase">[] }>;
  shortcuts?: Shortcut[];
}
