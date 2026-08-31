import { Component } from "preact";
import { CommandButton, ConsolePane } from "@xenorepo/ui";
import {
  MODULATION_TARGETS,
  PARAMETER_BOUNDS,
  acceptsAudio,
  createModule,
  defaultParameters,
  emitsAudio,
  emitsControl,
  validConnection,
  type Connection,
  type LabState,
  type ModuleKind,
  type ModuleNode,
} from "./model.js";

const MODULE_KINDS: readonly ModuleKind[] = [
  "waveform",
  "noise",
  "gain",
  "adsr",
  "filter",
  "saturation",
  "delay",
  "chorus",
  "reverb",
  "compressor",
  "mixer",
  "lfo",
  "output",
];
const CATEGORIES: Readonly<Partial<Record<ModuleKind, Readonly<Record<string, readonly string[]>>>>> = {
  filter: { mode: ["low-pass", "high-pass", "band-pass", "notch"] },
  noise: { color: ["white", "pink", "brown"] },
  lfo: { shape: ["sine", "triangle", "square", "saw"] },
};
const STEPS: Readonly<Record<string, number>> = {
  frequency: 10,
  detune: 1,
  threshold: 1,
  mode: 1,
  color: 1,
  shape: 1,
  ratio: 0.1,
  drive: 0.1,
  rate: 0.01,
};
type Pending = { from: string; type: "audio" | "modulation" };
type Drag = { id: string; dx: number; dy: number; pointerId: number };
interface CircuitProps {
  lab: LabState;
  commit: (lab: LabState) => void;
}
interface CircuitState {
  pending: Pending | null;
  notice: string;
  rejected: boolean;
}

function label(node: ModuleNode, modules: ModuleNode[]): string {
  const peers = modules.filter((item) => item.kind === node.kind);
  return `${node.kind[0]?.toUpperCase()}${node.kind.slice(1)} ${peers.findIndex((item) => item.id === node.id) + 1}`;
}
function edgeType(edge: Connection): "audio" | "modulation" {
  return edge.type ?? "audio";
}

export class CircuitPanel extends Component<CircuitProps, CircuitState> {
  override state: CircuitState = {
    pending: null,
    notice: "Select an output, then a compatible input.",
    rejected: false,
  };
  private drag: Drag | null = null;

  private announce(notice: string, rejected = false): void {
    this.setState({ notice, rejected });
  }
  private add(kind: ModuleKind): void {
    const index = this.props.lab.modules.length;
    const node = createModule(
      `${kind}-${crypto.randomUUID()}`,
      kind,
      20 + (index % 4) * 265,
      20 + Math.floor(index / 4) * 245,
    );
    this.props.commit({ ...this.props.lab, modules: [...this.props.lab.modules, node] });
    this.announce(`${label(node, [...this.props.lab.modules, node])} added.`);
  }
  private remove(node: ModuleNode): void {
    const lab = this.props.lab;
    const name = label(node, lab.modules);
    this.props.commit({
      ...lab,
      modules: lab.modules.filter((item) => item.id !== node.id),
      connections: lab.connections.filter((edge) => edge.from !== node.id && edge.to !== node.id),
    });
    this.setState({ pending: this.state.pending?.from === node.id ? null : this.state.pending });
    this.announce(`${name} and its attached cables removed.`);
  }
  private update(node: ModuleNode, name: string, parameter: number): void {
    const modules = this.props.lab.modules.map((item) =>
      item.id === node.id ? { ...item, parameters: { ...item.parameters, [name]: parameter } } : item,
    );
    this.props.commit({ ...this.props.lab, modules });
  }
  private reset(node: ModuleNode): void {
    const modules = this.props.lab.modules.map((item) =>
      item.id === node.id
        ? { ...item, parameters: defaultParameters(item.kind), ...(item.bypass === undefined ? {} : { bypass: false }) }
        : item,
    );
    this.props.commit({ ...this.props.lab, modules });
    this.announce(`${label(node, this.props.lab.modules)} reset.`);
  }
  private bypass(node: ModuleNode): void {
    const modules = this.props.lab.modules.map((item) =>
      item.id === node.id ? { ...item, bypass: !item.bypass } : item,
    );
    this.props.commit({ ...this.props.lab, modules });
    this.announce(`${label(node, this.props.lab.modules)} ${node.bypass ? "enabled" : "bypassed"}.`);
  }
  private selectOutput(node: ModuleNode, type: Pending["type"]): void {
    const next =
      this.state.pending?.from === node.id && this.state.pending.type === type ? null : { from: node.id, type };
    this.setState({ pending: next });
    this.announce(
      next ? `${label(node, this.props.lab.modules)} ${type} output selected.` : "Cable selection cleared.",
    );
  }
  private connect(node: ModuleNode, target?: string): void {
    const pending = this.state.pending;
    if (!pending) {
      this.announce("Select an output before an input.", true);
      return;
    }
    const edge: Connection = { from: pending.from, to: node.id, type: pending.type, ...(target ? { target } : {}) };
    if (!validConnection(this.props.lab.modules, edge, this.props.lab.connections)) {
      this.setState({ pending: null });
      this.announce("Connection rejected: incompatible, duplicate, or cyclic cable.", true);
      return;
    }
    this.props.commit({ ...this.props.lab, connections: [...this.props.lab.connections, edge] });
    this.setState({ pending: null });
    this.announce("Connection created.");
  }
  private disconnect(edge: Connection): void {
    this.props.commit({ ...this.props.lab, connections: this.props.lab.connections.filter((item) => item !== edge) });
    this.announce("Connection removed.");
  }
  private startDrag(event: PointerEvent, node: ModuleNode): void {
    if ((event.target as HTMLElement).closest("button,input,select,label")) return;
    const canvas = (event.currentTarget as HTMLElement).parentElement?.getBoundingClientRect();
    if (!canvas) return;
    this.drag = {
      id: node.id,
      dx: event.clientX - canvas.left - node.x,
      dy: event.clientY - canvas.top - node.y,
      pointerId: event.pointerId,
    };
    try {
      (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    } catch {
      /* Synthetic pointer. */
    }
  }
  private move = (event: PointerEvent): void => {
    if (!this.drag || this.drag.pointerId !== event.pointerId) return;
    const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const modules = this.props.lab.modules.map((node) =>
      node.id === this.drag?.id
        ? {
            ...node,
            x: Math.max(0, Math.min(bounds.width - 244, event.clientX - bounds.left - this.drag.dx)),
            y: Math.max(0, Math.min(bounds.height - 120, event.clientY - bounds.top - this.drag.dy)),
          }
        : node,
    );
    this.props.commit({ ...this.props.lab, modules });
  };
  private endDrag = (): void => {
    this.drag = null;
  };

  private parameter(node: ModuleNode, name: string) {
    const moduleName = label(node, this.props.lab.modules);
    const bounds = PARAMETER_BOUNDS[node.kind][name];
    if (!bounds) return null;
    const options = CATEGORIES[node.kind]?.[name];
    const current = node.parameters?.[name] ?? bounds[0];
    if (options)
      return (
        <label class="parameter">
          <span>{name}</span>
          <select
            data-ui-control="domain"
            aria-label={`${moduleName} ${name}`}
            value={current}
            onChange={(event) => this.update(node, name, Number(event.currentTarget.value))}
          >
            {options.map((option, index) => (
              <option value={index}>{option}</option>
            ))}
          </select>
        </label>
      );
    return (
      <label class="parameter">
        <span>{name}</span>
        <input
          data-ui-control="domain"
          aria-label={`${moduleName} ${name}`}
          type="range"
          min={bounds[0]}
          max={bounds[1]}
          step={STEPS[name] ?? 0.01}
          value={current}
          onInput={(event) => this.update(node, name, Number(event.currentTarget.value))}
        />
        <output>{Number(current.toFixed(2))}</output>
      </label>
    );
  }
  private module(node: ModuleNode) {
    const moduleName = label(node, this.props.lab.modules);
    const targets = MODULATION_TARGETS[node.kind] ?? [];
    return (
      <article
        class={`module ${node.kind}`}
        style={{ left: node.x, top: node.y }}
        role="region"
        aria-label={`${moduleName} module`}
        onPointerDown={(event) => this.startDrag(event, node)}
      >
        <header>
          <strong>{moduleName}</strong>
          <CommandButton aria-label={`Remove ${moduleName}`} onClick={() => this.remove(node)}>
            ×
          </CommandButton>
        </header>
        <div class="ports">
          {acceptsAudio(node.kind) && (
            <button
              data-ui-control="domain"
              aria-label={`${moduleName} audio input`}
              onClick={() => this.connect(node)}
            >
              AUDIO IN
            </button>
          )}
          {emitsAudio(node.kind) && (
            <button
              data-ui-control="domain"
              aria-label={`${moduleName} audio output`}
              aria-pressed={this.state.pending?.from === node.id && this.state.pending.type === "audio"}
              onClick={() => this.selectOutput(node, "audio")}
            >
              AUDIO OUT
            </button>
          )}
          {emitsControl(node.kind) && (
            <button
              data-ui-control="domain"
              aria-label={`${moduleName} modulation output`}
              aria-pressed={this.state.pending?.from === node.id && this.state.pending.type === "modulation"}
              onClick={() => this.selectOutput(node, "modulation")}
            >
              MOD OUT
            </button>
          )}
        </div>
        <div class="parameters">
          {Object.keys(PARAMETER_BOUNDS[node.kind]).map((name) => this.parameter(node, name))}
        </div>
        {targets.length > 0 && (
          <div class="mod-targets">
            {targets.map((target) => (
              <button
                data-ui-control="domain"
                aria-label={`${moduleName} ${target} modulation input`}
                onClick={() => this.connect(node, target)}
              >
                ↯ {target}
              </button>
            ))}
          </div>
        )}
        <footer>
          {node.bypass !== undefined && (
            <CommandButton
              aria-label={`Bypass ${moduleName}`}
              aria-pressed={node.bypass}
              onClick={() => this.bypass(node)}
            >
              BYPASS
            </CommandButton>
          )}
          <CommandButton aria-label={`Reset ${moduleName}`} onClick={() => this.reset(node)}>
            RESET
          </CommandButton>
        </footer>
      </article>
    );
  }

  override render() {
    const lab = this.props.lab;
    return (
      <ConsolePane class="circuit-pane" title="PATCH BAY" tone="orange" aria-label="Patch bay">
        <div class="module-tools" aria-label="Add circuit module">
          {MODULE_KINDS.map((kind) => (
            <CommandButton aria-label={`Add ${kind} module`} onClick={() => this.add(kind)}>
              + {kind.toUpperCase()}
            </CommandButton>
          ))}
        </div>
        <div class="circuit-scroll" tabIndex={0} aria-label="Scrollable modular circuit canvas">
          <div class="circuit" onPointerMove={this.move} onPointerUp={this.endDrag} onPointerCancel={this.endDrag}>
            <svg class="cables" aria-hidden="true">
              {lab.connections.map((edge) => {
                const from = lab.modules.find((node) => node.id === edge.from);
                const to = lab.modules.find((node) => node.id === edge.to);
                return from && to ? (
                  <line class={edgeType(edge)} x1={from.x + 244} y1={from.y + 46} x2={to.x} y2={to.y + 46} />
                ) : null;
              })}
            </svg>
            {lab.modules.map((node) => this.module(node))}
          </div>
        </div>
        <p class={this.state.rejected ? "patch-alert" : "patch-status"} role={this.state.rejected ? "alert" : "status"}>
          {this.state.notice}
        </p>
        <ol class="connections" aria-label="Connections">
          {lab.connections.map((edge) => {
            const from = lab.modules.find((node) => node.id === edge.from);
            const to = lab.modules.find((node) => node.id === edge.to);
            const text =
              from && to
                ? `${label(from, lab.modules)} ${edgeType(edge)} → ${label(to, lab.modules)}${edge.target ? ` ${edge.target}` : ""}`
                : "Unknown cable";
            return (
              <li>
                {text}
              <CommandButton
                aria-label={`Disconnect ${text}`}
                onClick={() => this.disconnect(edge)}
              >
                  disconnect
                </CommandButton>
              </li>
            );
          })}
        </ol>
      </ConsolePane>
    );
  }
}
