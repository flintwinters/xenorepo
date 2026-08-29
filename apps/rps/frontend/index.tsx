import { Component, render } from "preact";
import { loadSession, renameSession } from "./client.js";
import { ArenaTransport } from "./transport.js";
import type { LedgerEntry, Mode, Player, ServerEvent, Throw, Tone } from "./types.js";
import { ArenaView, type ArenaViewModel } from "./view.js";
import "./styles.css";
import "./effects.css";

interface ArenaState extends ArenaViewModel {
  mode: Mode;
  player?: Player | undefined;
  submitted: boolean;
  watched?: string | undefined;
  completedMatchId?: string | undefined;
  rematchRequested: boolean;
  deadline?: string | undefined;
}

const initialState: ArenaState = {
  landing: true,
  online: false,
  landingMessage: "CONNECTING",
  landingError: false,
  nickname: "",
  playEnabled: false,
  visitors: 0,
  queueSize: 0,
  activeMatches: 0,
  matches: [],
  recent: [],
  signal: "idle",
  queueLabel: "JOIN QUEUE",
  queueDisabled: true,
  rematchVisible: false,
  rematchDisabled: true,
  opponentLabel: "OPPONENT",
  youLabel: "YOU",
  opponentName: "——",
  opponentStreak: 0,
  playerName: "——",
  playerStreak: 0,
  opponentReady: false,
  playerReady: false,
  clock: 10,
  roundLabel: "STANDBY",
  standby: "AWAITING MATCH",
  searching: false,
  throwEnabled: false,
  message: "CONNECTING",
  ties: 0,
  rounds: [],
  mode: "idle",
  submitted: false,
  rematchRequested: false,
};

const resultTone = (result: string): Tone => (result === "WIN" ? "win" : result === "LOSS" ? "loss" : "tie");

function rematchAvailable(state: ArenaState): boolean {
  return state.mode === "complete" && !state.watched && Boolean(state.completedMatchId);
}

function eventThrows(event: Extract<ServerEvent, { type: "round_reveal" }>): [Throw, Throw] {
  const [first = "rock", second = "rock"] = Object.values(event.throws);
  return [first, second];
}

function revealSelections(event: Extract<ServerEvent, { type: "round_reveal" }>, playerId?: string): [Throw, Throw] {
  const [first, second] = eventThrows(event);
  const mine = event.throws[playerId ?? ""] ?? first;
  if (!event.throws[playerId ?? ""]) return [mine, second];
  const theirs = Object.entries(event.throws).find(([id]) => id !== playerId)?.[1] ?? second;
  return [mine, theirs];
}

function revealResult(event: Extract<ServerEvent, { type: "round_reveal" }>, state: ArenaState): string {
  if (event.outcome === "tie") return "TIE";
  if (state.watched) return "DECISIVE";
  return event.winner_id === state.player?.id ? "WIN" : "LOSS";
}

function finishLabel(event: Extract<ServerEvent, { type: "match_result" }>, state: ArenaState): string {
  if (event.outcome === "draw") return "MATCH DRAW";
  const winner = event.participants?.find((player) => player.id === event.winner_id);
  if (state.watched) return `${winner?.nickname ?? "PLAYER"} WINS`;
  return event.winner_id === state.player?.id ? "MATCH WON" : "MATCH LOST";
}

function finishTone(event: Extract<ServerEvent, { type: "match_result" }>, state: ArenaState): Tone {
  if (event.outcome === "draw") return "tie";
  return state.watched || event.winner_id === state.player?.id ? "win" : "loss";
}

export class ArenaApp extends Component<Record<string, never>, ArenaState> {
  override state = initialState;
  private transport = new ArenaTransport({
    opened: () => this.opened(),
    event: (event) => this.apply(event),
    closed: () => this.closed(),
  });
  private timer?: number;

  override componentDidMount(): void {
    document.title = "Rock Paper Scissors";
    document.addEventListener("keydown", this.keydown);
    void this.connect();
  }

  override componentWillUnmount(): void {
    document.removeEventListener("keydown", this.keydown);
    window.clearInterval(this.timer);
    this.transport.disconnect();
  }

  private async connect(): Promise<void> {
    try {
      this.setPlayer(await loadSession());
      this.transport.connect();
    } catch (failure) {
      const error = failure as Error & { status?: number };
      this.fail(error.message);
      if (error.status === 404) this.setState({ landingMessage: "● WRONG SERVICE" });
      else window.setTimeout(() => void this.connect(), 2000);
    }
  }

  private opened(): void {
    this.setState({ online: true, landingMessage: "READY", landingError: false }, () => this.controls());
  }

  private closed(): void {
    this.setState({ online: false, landingMessage: "● RECONNECTING" });
    if (!this.state.landing) this.announce("CONNECTION LOST · RECONNECTING", "error");
    this.controls();
  }

  private controls(): void {
    const { mode, submitted, rematchRequested, online, nickname } = this.state;
    const rematchVisible = rematchAvailable(this.state);
    this.setState({
      playEnabled: online && nickname.length >= 2,
      throwEnabled: mode === "match" && !submitted,
      queueDisabled: !online || mode === "match" || mode === "spectating",
      queueLabel: mode === "queued" ? "LEAVE QUEUE" : "JOIN QUEUE",
      rematchVisible,
      rematchDisabled: !rematchVisible || rematchRequested || !online,
    });
  }

  private announce(message: string, signal: Tone = "active"): void {
    this.setState({ message, signal });
  }

  private fail(message: string): void {
    if (this.state.landing) this.setState({ landingMessage: message, landingError: true });
    else this.announce(message, "error");
  }

  private send(type: string, data: object = {}): void {
    if (!this.transport.send(type, data)) this.fail("CONNECTION LOST");
  }

  private setPlayer(player: Player): void {
    this.setState(
      {
        player,
        playerName: player.nickname,
        playerStreak: player.competitive_streak,
        nickname: this.state.landing ? this.state.nickname : player.nickname,
      },
      () => this.controls(),
    );
  }

  private clock(deadline: string): void {
    window.clearInterval(this.timer);
    const tick = () => {
      const remaining = Math.max(0, Math.ceil((Date.parse(deadline) - Date.now()) / 1000));
      this.setState({ clock: remaining });
      if (!remaining) window.clearInterval(this.timer);
    };
    tick();
    this.timer = window.setInterval(tick, 200);
  }

  private apply(event: ServerEvent): void {
    const handlers: Record<ServerEvent["type"], (value: any) => void> = {
      session: (value) => this.setPlayer(value.player),
      arena_snapshot: (value) => this.snapshot(value),
      queue_state: (value) => this.queueState(value.queued),
      match_assignment: (value) => this.match(value.opponent),
      round_state: (value) => this.round(value),
      spectator_state: (value) => this.spectator(value),
      spectator_count: (value) => this.announce(`SPECTATING · ${value.count} VIEWING`),
      round_reveal: (value) => this.reveal(value),
      match_result: (value) => this.finish(value),
      rematch_requested: () =>
        this.setState({ rematchRequested: true }, () => this.announce("REMATCH REQUESTED", "ready")),
      error: (value) => this.fail(value.message),
    };
    handlers[event.type](event);
    this.controls();
  }

  private snapshot(event: Extract<ServerEvent, { type: "arena_snapshot" }>): void {
    this.setState({
      visitors: event.visitors,
      queueSize: event.queue_size,
      activeMatches: event.active_matches,
      matches: event.top_matches,
      recent: event.recent_results,
    });
  }

  private queueState(queued: boolean): void {
    const standby = queued ? "SEARCHING FOR OPPONENT" : "READY TO JOIN QUEUE";
    this.setState({ landing: false, mode: queued ? "queued" : "idle", searching: queued, standby });
    this.announce(queued ? "MATCHMAKING · SEARCHING FOR OPPONENT" : "QUEUE LEFT · READY", queued ? "search" : "idle");
  }

  private match(opponent: Player): void {
    const standby = `MATCH START · ${this.state.player?.nickname ?? "YOU"} VS ${opponent.nickname}`;
    this.setState({
      landing: false,
      mode: "match",
      watched: undefined,
      ties: 0,
      rounds: [],
      submitted: false,
      selected: undefined,
      reveal: undefined,
      searching: false,
      opponentLabel: "OPPONENT",
      youLabel: "YOU",
      opponentName: opponent.nickname,
      opponentStreak: opponent.competitive_streak,
      standby,
    });
    this.announce(`MATCH START · YOU VS ${opponent.nickname}`);
  }

  private round(event: Extract<ServerEvent, { type: "round_state" }>): void {
    const standby = event.submitted
      ? "YOUR THROW LOCKED · WAITING FOR OPPONENT"
      : event.opponent_submitted
        ? "OPPONENT READY · YOUR THROW"
        : event.round === 1
          ? "MATCH START · CHOOSE YOUR THROW"
          : `ROUND ${event.round} OPEN · LAST ${this.state.rounds[0]?.result ?? "TIE"}`;
    const signal: Tone = event.submitted ? "locked" : event.opponent_submitted ? "ready" : "active";
    this.setState({
      landing: false,
      mode: "match",
      submitted: event.submitted,
      selected: undefined,
      reveal: undefined,
      searching: false,
      roundLabel: `ROUND ${event.round}`,
      opponentReady: event.opponent_submitted,
      playerReady: event.submitted,
      standby,
    });
    this.announce(standby, signal);
    this.clock(event.deadline);
  }

  private spectator(event: Extract<ServerEvent, { type: "spectator_state" }>): void {
    const [first, second] = event.participants;
    const rounds: LedgerEntry[] = event.revealed_rounds
      .map((item) => {
        const values = Object.values(item.throws) as [Throw, Throw];
        return {
          round: item.round,
          mine: values[0].toUpperCase(),
          theirs: values[1].toUpperCase(),
          result: item.outcome.toUpperCase(),
        };
      })
      .reverse();
    this.setState({
      landing: false,
      mode: "spectating",
      submitted: true,
      watched: event.match_id,
      searching: false,
      opponentLabel: "PLAYER A",
      youLabel: "PLAYER B",
      playerName: first.nickname,
      playerStreak: first.competitive_streak,
      opponentName: second.nickname,
      opponentStreak: second.competitive_streak,
      roundLabel: `ROUND ${event.round}`,
      ties: event.tie_count,
      rounds,
    });
    this.announce(`WATCHING ${first.nickname} VS ${second.nickname} · ${event.spectator_count} VIEWING`);
    this.clock(event.deadline);
  }

  private reveal(event: Extract<ServerEvent, { type: "round_reveal" }>): void {
    window.clearInterval(this.timer);
    const [mine, theirs] = revealSelections(event, this.state.player?.id);
    const result = revealResult(event, this.state);
    const entry = { round: event.round, mine: mine.toUpperCase(), theirs: theirs.toUpperCase(), result };
    this.setState((state) => ({
      submitted: true,
      reveal: { mine, theirs, result, animation: Date.now() },
      ties: state.ties + (event.outcome === "tie" ? 1 : 0),
      rounds: [entry, ...state.rounds],
    }));
    this.announce(`ROUND ${event.round} · ${result}`, resultTone(result));
  }

  private finish(event: Extract<ServerEvent, { type: "match_result" }>): void {
    window.clearInterval(this.timer);
    const label = finishLabel(event, this.state);
    const signal = finishTone(event, this.state);
    if (event.player) this.setPlayer(event.player);
    this.setState({
      mode: "complete",
      completedMatchId: event.id,
      rematchRequested: false,
      submitted: true,
      opponentReady: false,
      playerReady: false,
      roundLabel: "FINAL",
    });
    this.announce(this.state.watched ? label : `${label} · REQUEUING`, signal);
  }

  private keydown = (event: KeyboardEvent): void => {
    if (event.repeat || event.target instanceof HTMLInputElement) return;
    const selection = (
      { "1": "rock", r: "rock", "2": "paper", p: "paper", "3": "scissors", s: "scissors" } as Record<string, Throw>
    )[event.key.toLowerCase()];
    if (selection && this.state.throwEnabled) this.choose(selection);
  };

  private choose = (selection: Throw): void => {
    this.setState({ submitted: true, selected: selection }, () => this.controls());
    this.announce(`${selection.toUpperCase()} LOCKED · WAITING FOR OPPONENT`, "locked");
    this.send("throw", { selection });
  };

  override render() {
    const actions = {
      nickname: (nickname: string) => this.setState({ nickname }, () => this.controls()),
      play: (event: Event) => {
        event.preventDefault();
        void this.play();
      },
      queue: () => this.send(this.state.mode === "queued" ? "queue_leave" : "queue_join"),
      rematch: () => this.send("rematch", { match_id: this.state.completedMatchId }),
      watch: (match_id: string) => {
        this.setState({ landing: false });
        this.send("spectate", { match_id });
      },
      choose: this.choose,
    };
    return <ArenaView model={this.state} actions={actions} />;
  }

  private async play(): Promise<void> {
    try {
      this.setPlayer(await renameSession(this.state.nickname));
      this.setState({ landing: false, mode: "queued" }, () => this.controls());
      this.send("queue_join");
    } catch (failure) {
      this.fail((failure as Error).message);
    }
  }
}

export function mount(root: HTMLElement | null): void {
  if (!root) throw new Error("missing application mount");
  render(<ArenaApp />, root);
}
