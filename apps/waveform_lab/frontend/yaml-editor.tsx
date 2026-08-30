import { basicSetup } from "codemirror";
import { yaml } from "@codemirror/lang-yaml";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { Component } from "preact";
import { CommandButton, ConsolePane } from "@xenorepo/ui";
import { applySynth, encodeSynth } from "./state-yaml.js";
import { gruvbox } from "./gruvbox.js";
import type { LabState } from "./model.js";

interface Props { lab: LabState; commit: (lab: LabState) => void; }
interface State { notice: string; rejected: boolean; dirty: boolean; }

export class SynthYamlEditor extends Component<Props, State> {
  override state: State = { notice: "YAML matches the live synth setup.", rejected: false, dirty: false };
  private host: HTMLDivElement | null = null;
  private editor: EditorView | null = null;
  private replacing = false;

  override componentDidMount(): void {
    if (!this.host) return;
    this.editor = new EditorView({ parent: this.host, state: EditorState.create({
      doc: encodeSynth(this.props.lab),
      extensions: [basicSetup, history(), keymap.of([...defaultKeymap, ...historyKeymap]), yaml(), ...gruvbox,
        EditorView.lineWrapping, EditorView.updateListener.of((update) => {
          if (update.docChanged && !this.replacing)
            this.setState({ dirty: true, notice: "Draft differs from the live synth.", rejected: false });
        })],
    }) });
  }
  override componentDidUpdate(previous: Props): void {
    if (previous.lab !== this.props.lab && !this.state.dirty) this.replace(encodeSynth(this.props.lab));
  }
  override componentWillUnmount(): void { this.editor?.destroy(); }

  private replace(source: string): void {
    if (!this.editor) return;
    if (this.editor.state.doc.toString() === source) return;
    this.replacing = true;
    this.editor.dispatch({ changes: { from: 0, to: this.editor.state.doc.length, insert: source } });
    this.replacing = false;
    this.setState({ dirty: false });
  }
  private apply = (): void => {
    if (!this.editor) return;
    try {
      const next = applySynth(this.editor.state.doc.toString(), this.props.lab);
      this.props.commit(next); this.replace(encodeSynth(next));
      this.setState({ notice: "Synth YAML applied and saved.", rejected: false, dirty: false });
    } catch (error) {
      this.setState({ notice: error instanceof Error ? error.message : "Synth YAML is invalid.", rejected: true });
    }
  };
  private revert = (): void => {
    this.replace(encodeSynth(this.props.lab));
    this.setState({ notice: "Draft restored from the live synth.", rejected: false, dirty: false });
  };

  override render() {
    return <ConsolePane class="yaml-pane" title="SYNTH SETUP / YAML" tone="blue">
      <div class="yaml-toolbar"><CommandButton onClick={this.apply}>APPLY YAML</CommandButton>
        <CommandButton disabled={!this.state.dirty} onClick={this.revert}>REVERT DRAFT</CommandButton>
        <span>LOOP STATE REMAINS GUI-ONLY</span></div>
      <div class="yaml-editor" aria-label="Synth setup YAML editor" ref={(element) => { this.host = element; }} />
      <p class={this.state.rejected ? "yaml-alert" : "yaml-status"} role={this.state.rejected ? "alert" : "status"}>
        {this.state.notice}</p>
    </ConsolePane>;
  }
}
