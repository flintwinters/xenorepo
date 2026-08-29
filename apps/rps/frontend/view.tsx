import type { ComponentChildren } from "preact";
import type { LedgerEntry, MatchListing, RecentResult, Throw } from "./types.js";

export interface ArenaViewModel {
  landing: boolean;
  online: boolean;
  landingMessage: string;
  landingError: boolean;
  nickname: string;
  playEnabled: boolean;
  visitors: number;
  queueSize: number;
  activeMatches: number;
  matches: MatchListing[];
  recent: RecentResult[];
  signal: string;
  queueLabel: string;
  queueDisabled: boolean;
  rematchVisible: boolean;
  rematchDisabled: boolean;
  opponentLabel: string;
  youLabel: string;
  opponentName: string;
  opponentStreak: number;
  playerName: string;
  playerStreak: number;
  opponentReady: boolean;
  playerReady: boolean;
  clock: number;
  roundLabel: string;
  standby: string;
  searching: boolean;
  reveal?: { mine: Throw; theirs: Throw; result: string; animation: number } | undefined;
  throwEnabled: boolean;
  selected?: Throw | undefined;
  message: string;
  ties: number;
  rounds: LedgerEntry[];
}

export interface ArenaActions {
  nickname(value: string): void;
  play(event: Event): void;
  queue(): void;
  rematch(): void;
  watch(matchId: string): void;
  choose(selection: Throw): void;
}

const icons: Record<Throw, string> = { rock: "🪨", paper: "📄", scissors: "✂️" };

function MatchList({ matches, watch }: { matches: MatchListing[]; watch(id: string): void }) {
  if (!matches.length) return <li>NO ACTIVE MATCHES</li>;
  return (
    <>
      {matches.map((match) => (
        <li key={match.match_id}>
          <div>
            {match.participants.map((player) => (
              <div class="match-player" key={player.id}>
                <span>{player.nickname}</span>
                <span>STREAK {player.competitive_streak}</span>
              </div>
            ))}
            <div class="match-meta">
              {match.ranked ? "RANKED" : "UNRANKED"} · {match.spectator_count} VIEWING
            </div>
          </div>
          <button class="key" data-watch={match.match_id} onClick={() => watch(match.match_id)}>
            WATCH
          </button>
        </li>
      ))}
    </>
  );
}

function Pane({
  title,
  tone = "",
  children,
  className = "",
}: {
  title: ComponentChildren;
  tone?: string;
  children: ComponentChildren;
  className?: string;
}) {
  return (
    <section class={`pane ${className}`}>
      <h2 class={`pane-title ${tone}`}>{title}</h2>
      {children}
    </section>
  );
}

export function ArenaView({ model, actions }: { model: ArenaViewModel; actions: ArenaActions }) {
  if (model.landing)
    return (
      <section class="landing" id="landing">
        <header class="landing-utility">
          <span class="brand">Rock Paper Scissors</span>
          <div class="landing-stats">
            <span>
              <strong id="landing-online">{model.visitors}</strong> ONLINE
            </span>
            <span>
              <strong id="landing-active">{model.activeMatches}</strong> MATCHES
            </span>
          </div>
        </header>
        <main class="landing-mosaic">
          <Pane title="ENTER ARENA" tone="green">
            <div class="entry-body">
              <div class="mark">Rock Paper Scissors</div>
              <form class="play-form" id="play-form" onSubmit={actions.play}>
                <label>
                  DISPLAY NAME
                  <input
                    id="nickname"
                    minlength={2}
                    maxlength={24}
                    required
                    autocomplete="nickname"
                    value={model.nickname}
                    onInput={(event) => actions.nickname(event.currentTarget.value)}
                  />
                </label>
                <button class="key play" id="play" disabled={!model.playEnabled}>
                  PLAY
                </button>
              </form>
            </div>
          </Pane>
          <Pane title="ONGOING MATCHES" tone="purple" className="landing-live">
            <ul class="pane-body public-list" id="landing-matches">
              <MatchList matches={model.matches} watch={actions.watch} />
            </ul>
          </Pane>
        </main>
        <footer class="landing-status">
          <span id="landing-message" class={model.landingError ? "error" : ""} role="status">
            {model.landingMessage}
          </span>
          <span>THROW/98</span>
        </footer>
      </section>
    );

  const reveal = model.reveal;
  return (
    <main class={`frame signal-${model.signal}`} id="arena-view">
      <header class="utility">
        <span class="brand">Rock Paper Scissors</span>
        <button
          class="key"
          id="rematch"
          hidden={!model.rematchVisible}
          disabled={model.rematchDisabled}
          onClick={actions.rematch}
        >
          REMATCH
        </button>
        <button class="key" id="queue" disabled={model.queueDisabled} onClick={actions.queue}>
          {model.queueLabel}
        </button>
        <span class={`link ${model.online ? "" : "offline"}`} id="link">
          ● {model.online ? "ONLINE" : "RECONNECTING"}
        </span>
      </header>
      <section class="mosaic">
        <aside class="pane arena-index">
          <h2 class="pane-title">ARENA</h2>
          <div class="pane-body">
            <dl class="metrics">
              <dt>VISITORS</dt>
              <dd id="online">{model.visitors}</dd>
              <dt>QUEUE</dt>
              <dd id="queue-size">{model.queueSize}</dd>
              <dt>ACTIVE</dt>
              <dd id="active-count">{model.activeMatches}</dd>
            </dl>
            <div class="public-title">TOP MATCHES</div>
            <ul class="public-list" id="top-matches">
              <MatchList matches={model.matches} watch={actions.watch} />
            </ul>
            <div class="public-title">RECENT</div>
            <div id="recent-results">
              {model.recent.length ? (
                model.recent.map((result, index) => {
                  const winner = result.participants.find((player) => player.id === result.winner_id);
                  return (
                    <div class="activity" key={index}>
                      {result.outcome.toUpperCase()} · {winner?.nickname ?? "DRAW"}
                    </div>
                  );
                })
              ) : (
                <div class="activity">NO RESULTS</div>
              )}
            </div>
          </div>
        </aside>
        <Pane
          title={
            <>
              THROW CONTROL{" "}
              <span class="title-meta" id="ties">
                TIES {model.ties} / 5
              </span>
            </>
          }
          tone="green"
          className="battle"
        >
          <div class="battle-body">
            <div class={`player-strip opponent ${model.opponentReady ? "ready" : ""}`} id="opponent-strip">
              <div>
                <div class="label" id="opponent-label">
                  {model.opponentLabel}
                </div>
                <div class="name" id="opponent">
                  {model.opponentName}
                </div>
              </div>
              <div class="streak">
                STREAK <span id="opponent-streak">{model.opponentStreak}</span>
              </div>
            </div>
            <div class="instrument">
              <div class="timer">
                <div class={`clock ${model.clock <= 3 ? "low" : ""}`} id="clock">
                  {model.clock}
                </div>
                <div class="round" id="round">
                  {model.roundLabel}
                </div>
              </div>
              {!reveal && (
                <div class={`standby ${model.searching ? "searching" : ""}`} id="standby">
                  {model.standby}
                </div>
              )}
              {reveal && (
                <div
                  key={reveal.animation}
                  class={`result result-${reveal.result.toLowerCase()} result-reveal`}
                  id="result"
                >
                  <div>
                    <div class="label">THEIR THROW</div>
                    <div class="pick" id="their-pick">
                      {icons[reveal.theirs]}
                    </div>
                  </div>
                  <div class="outcome" id="outcome">
                    {reveal.result}
                  </div>
                  <div>
                    <div class="label">YOUR THROW</div>
                    <div class="pick" id="your-pick">
                      {icons[reveal.mine]}
                    </div>
                  </div>
                </div>
              )}
            </div>
            <div class="throws">
              {(["rock", "paper", "scissors"] as Throw[]).map((selection, index) => (
                <button
                  class={`key throw ${model.selected === selection ? "selected" : ""}`}
                  data-throw={selection}
                  disabled={!model.throwEnabled}
                  onClick={() => actions.choose(selection)}
                  key={selection}
                >
                  <span>{["●", "▰", "✕"][index]}</span>
                  <span>{selection.toUpperCase()}</span>
                  <span class="shortcut">
                    {index + 1} / {selection.charAt(0).toUpperCase()}
                  </span>
                </button>
              ))}
            </div>
            <div class="message message-announce" id="message" role="status">
              {model.message}
            </div>
            <div class={`player-strip you ${model.playerReady ? "ready" : ""}`} id="you-strip">
              <div>
                <div class="label" id="you-label">
                  {model.youLabel}
                </div>
                <div class="name" id="your-name">
                  {model.playerName}
                </div>
              </div>
              <div class="streak">
                STREAK <span id="your-streak">{model.playerStreak}</span>
              </div>
            </div>
          </div>
        </Pane>
        <Pane
          title={
            <>
              ROUNDS{" "}
              <span class="title-meta" id="ledger-count">
                {model.rounds.length} ENTRIES
              </span>
            </>
          }
          tone="purple"
          className="ledger"
        >
          <div class="pane-body">
            <table>
              <thead>
                <tr>
                  <th>SEQ</th>
                  <th>ROUND</th>
                  <th>YOU</th>
                  <th>THEM</th>
                  <th>RESULT</th>
                </tr>
              </thead>
              <tbody id="round-log">
                {model.rounds.length ? (
                  model.rounds.map((entry, index) => (
                    <tr key={`${entry.round}-${index}`}>
                      <td>{model.rounds.length - index}</td>
                      <td>{entry.round}</td>
                      <td>{entry.mine}</td>
                      <td>{entry.theirs}</td>
                      <td>{entry.result}</td>
                    </tr>
                  ))
                ) : (
                  <tr class="empty">
                    <td colspan={5}>NO RESOLVED ROUNDS</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Pane>
      </section>
    </main>
  );
}
