import { Component, render } from "preact";
import { CommandButton } from "@xenorepo/ui";
import "./styles.css";

const dimensions = ["FOCUS", "STRUCTURE", "CONNECTION", "ADAPTABILITY"] as const;
type Dimension = (typeof dimensions)[number];
interface Item {
  dimension: Dimension;
  text: string;
}
interface Response {
  index: number;
  value: number;
}
interface InventoryState {
  index: number;
  responses: Response[];
}

const items: Item[] = [
  { dimension: "FOCUS", text: "I can sustain attention on a demanding task without frequent switching." },
  { dimension: "STRUCTURE", text: "I prefer to make a clear plan before beginning unfamiliar work." },
  { dimension: "CONNECTION", text: "I gain energy from working through ideas with other people." },
  { dimension: "ADAPTABILITY", text: "I remain effective when a plan changes at short notice." },
  { dimension: "FOCUS", text: "I am comfortable setting aside distractions to complete a priority." },
  { dimension: "STRUCTURE", text: "I keep my work organized so that others can easily follow it." },
  { dimension: "CONNECTION", text: "I actively seek perspectives that differ from my own." },
  { dimension: "ADAPTABILITY", text: "I enjoy learning a new approach when the current one is not working." },
];
const labels = ["Strongly disagree", "Disagree", "Neither", "Agree", "Strongly agree"];

function score(responses: Response[], dimension: Dimension): number | null {
  const values = responses.filter(({ index }) => items[index]?.dimension === dimension).map(({ value }) => value);
  return values.length ? Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 20) : null;
}

class Inventory extends Component<Record<string, never>, InventoryState> {
  override state: InventoryState = { index: 0, responses: [] };

  override componentDidMount(): void {
    window.addEventListener("keydown", this.onKeydown);
  }
  override componentWillUnmount(): void {
    window.removeEventListener("keydown", this.onKeydown);
  }

  private record = (value: number): void => {
    if (this.state.index >= items.length) return;
    const responses = [...this.state.responses];
    responses[this.state.index] = { index: this.state.index, value };
    this.setState({ responses });
  };

  private next = (): void => {
    if (this.state.responses[this.state.index]) this.setState(({ index }) => ({ index: index + 1 }));
  };

  private restart = (): void => {
    this.setState({ index: 0, responses: [] });
  };

  private onKeydown = (event: KeyboardEvent): void => {
    if (event.key >= "1" && event.key <= "5" && this.state.index < items.length) this.record(Number(event.key));
    else if (event.key === "Enter") this.next();
    else if (event.key.toLowerCase() === "r") this.restart();
    else return;
    event.preventDefault();
  };

  override render() {
    const { index, responses } = this.state;
    const complete = index === items.length;
    const scores = Object.fromEntries(
      dimensions.map((dimension) => [dimension, score(responses, dimension)]),
    ) as Record<Dimension, number | null>;
    const strongest = dimensions.reduce((best, dimension) =>
      (scores[dimension] ?? 0) > (scores[best] ?? 0) ? dimension : best,
    );
    const current = items[index] ?? items[0]!;
    return (
      <main class="inventory" aria-label="Working Style Inventory">
        <header class="utility">
          <span class="brand">◈ WORKING STYLE</span>
          <span class="context">SELF-REFLECTION / EIGHT ITEMS</span>
          <span class="live">{complete ? "COMPLETE" : "READY"}</span>
          <CommandButton onClick={this.restart}>RESTART</CommandButton>
        </header>
        <section class="grid">
          <aside class="pane bank">
            <h2 class="pane-title">ITEMS</h2>
            <ol class="item-list">
              {items.map((_, itemIndex) => (
                <li class={itemIndex === index && !complete ? "active" : ""}>
                  <span class="number">{String(itemIndex + 1).padStart(2, "0")}</span>
                  <span>{responses[itemIndex] ? "RECORDED" : "PENDING"}</span>
                </li>
              ))}
            </ol>
          </aside>
          <section class="pane arena">
            <h2 class="pane-title">RESPONSE</h2>
            <div class="question-area">
              <div class="progress">
                <span>{complete ? "PROFILE COMPLETE" : `ITEM ${index + 1} / ${items.length}`}</span>
                <span>{complete ? strongest : current.dimension}</span>
              </div>
              <h1 class="prompt">
                {complete ? `Your strongest current signal is ${strongest.toLowerCase()}.` : current.text}
              </h1>
              <div class="answers" aria-live="polite">
                {complete ? (
                  <CommandButton onClick={this.restart}>START AGAIN</CommandButton>
                ) : (
                  labels.map((label, answerIndex) => (
                    <button
                      data-ui-control="domain"
                      class={`answer ${responses[index]?.value === answerIndex + 1 ? "selected" : ""}`}
                      onClick={() => this.record(answerIndex + 1)}
                    >
                      <span class="keynum">{answerIndex + 1}</span>
                      {label}
                    </button>
                  ))
                )}
              </div>
            </div>
          </section>
          <aside class="pane profile">
            <h2 class="pane-title">PROFILE</h2>
            <div class="profile-card">
              <dl>
                {dimensions.map((dimension) => (
                  <>
                    <dt>{dimension}</dt>
                    <dd>{scores[dimension] === null ? "—" : `${scores[dimension]}%`}</dd>
                  </>
                ))}
              </dl>
              <div class="meter">
                <i style={{ width: `${(responses.length / items.length) * 100}%` }} />
              </div>
              <div class="status-message">
                {complete ? (
                  <>
                    <strong>Profile recorded.</strong>
                    This brief inventory supports reflection, not diagnosis or selection decisions.
                  </>
                ) : responses[index] ? (
                  <>
                    <strong>Response recorded.</strong>Press Enter to continue, or choose another response.
                  </>
                ) : (
                  <>
                    <strong>There are no right answers.</strong>Choose the response that fits you best.
                  </>
                )}
              </div>
            </div>
          </aside>
          <section class="pane review">
            <h2 class="pane-title">RESPONSE LOG</h2>
            <div class="pane-body">
              <ol class="review-list">
                {responses.length ? (
                  responses.map((response, responseIndex) => (
                    <li>
                      <span class="number">{String(responseIndex + 1).padStart(2, "0")}</span>
                      <span>{items[responseIndex]?.text}</span>
                      <span class="result">{labels[response.value - 1]?.toUpperCase()}</span>
                    </li>
                  ))
                ) : (
                  <li>
                    <span class="muted">—</span>
                    <span class="muted">Your responses will appear here.</span>
                    <span class="result">WAITING</span>
                  </li>
                )}
              </ol>
            </div>
          </section>
        </section>
        <footer class="status">
          <span>
            <strong>● PRIVATE LOCAL SESSION</strong>
            {" · NOT A CLINICAL ASSESSMENT"}
          </span>
          <span class="hint">1–5 SELECT · ENTER CONTINUE · R RESTART</span>
          <span>{responses.length} RECORDED</span>
        </footer>
      </main>
    );
  }
}

export function mount(root: HTMLElement): void {
  document.title = "Working Style Inventory";
  render(<Inventory />, root);
}
