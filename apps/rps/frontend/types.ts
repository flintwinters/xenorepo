export type Throw = "rock" | "paper" | "scissors";
export type Tone = "idle" | "search" | "active" | "locked" | "ready" | "win" | "loss" | "tie" | "error";
export type Mode = "idle" | "queued" | "match" | "spectating" | "complete";

export interface Player {
  id: string;
  nickname: string;
  competitive_streak: number;
}

export interface Reveal {
  round: number;
  throws: Record<string, Throw>;
  outcome: "tie" | "decisive";
  winner_id?: string | null;
}

export interface MatchListing {
  match_id: string;
  ranked: boolean;
  participants: [Player, Player];
  spectator_count: number;
}

export interface RecentResult {
  outcome: string;
  winner_id?: string | null;
  participants: [Player, Player];
}

export type ServerEvent =
  | { type: "session"; player: Player }
  | {
      type: "arena_snapshot";
      visitors: number;
      queue_size: number;
      active_matches: number;
      top_matches: MatchListing[];
      recent_results: RecentResult[];
    }
  | { type: "queue_state"; queued: boolean }
  | { type: "match_assignment"; match_id: string; opponent: Player }
  | { type: "round_state"; round: number; deadline: string; submitted: boolean; opponent_submitted: boolean }
  | {
      type: "spectator_state";
      match_id: string;
      participants: [Player, Player];
      round: number;
      deadline: string;
      tie_count: number;
      revealed_rounds: Reveal[];
      spectator_count: number;
    }
  | ({ type: "round_reveal" } & Reveal)
  | {
      type: "match_result";
      id?: string;
      outcome: string;
      winner_id?: string | null;
      participants?: [Player, Player];
      player?: Player;
    }
  | { type: "spectator_count"; count: number }
  | { type: "rematch_requested"; match_id: string }
  | { type: "error"; message: string };

const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null;
const string = (value: unknown): value is string => typeof value === "string";
const number = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const player = (value: unknown): value is Player =>
  record(value) && string(value.id) && string(value.nickname) && number(value.competitive_streak);
const players = (value: unknown): value is [Player, Player] =>
  Array.isArray(value) && value.length === 2 && value.every(player);
const throws = (value: unknown): value is Record<string, Throw> =>
  record(value) && Object.values(value).every((item) => item === "rock" || item === "paper" || item === "scissors");

function reveal(value: Record<string, unknown>): boolean {
  return number(value.round) && throws(value.throws) && (value.outcome === "tie" || value.outcome === "decisive");
}

function matchListing(value: unknown): value is MatchListing {
  return (
    record(value) &&
    string(value.match_id) &&
    typeof value.ranked === "boolean" &&
    players(value.participants) &&
    number(value.spectator_count)
  );
}

function recentResult(value: unknown): value is RecentResult {
  return record(value) && string(value.outcome) && players(value.participants);
}

function arenaSnapshot(value: Record<string, unknown>): boolean {
  return (
    number(value.visitors) &&
    number(value.queue_size) &&
    number(value.active_matches) &&
    Array.isArray(value.top_matches) &&
    value.top_matches.every(matchListing) &&
    Array.isArray(value.recent_results) &&
    value.recent_results.every(recentResult)
  );
}

function spectatorState(value: Record<string, unknown>): boolean {
  return (
    string(value.match_id) &&
    players(value.participants) &&
    number(value.round) &&
    string(value.deadline) &&
    number(value.tie_count) &&
    number(value.spectator_count) &&
    Array.isArray(value.revealed_rounds) &&
    value.revealed_rounds.every((item) => record(item) && reveal(item))
  );
}

function matchResult(value: Record<string, unknown>): boolean {
  if (!string(value.outcome)) return false;
  if (value.participants !== undefined && !players(value.participants)) return false;
  if (value.player !== undefined && !player(value.player)) return false;
  return value.winner_id === undefined || value.winner_id === null || string(value.winner_id);
}

const parsers: Record<string, (value: Record<string, unknown>) => boolean> = {
  session: (v) => player(v.player),
  arena_snapshot: arenaSnapshot,
  queue_state: (v) => typeof v.queued === "boolean",
  match_assignment: (v) => string(v.match_id) && player(v.opponent),
  round_state: (v) =>
    number(v.round) &&
    string(v.deadline) &&
    typeof v.submitted === "boolean" &&
    typeof v.opponent_submitted === "boolean",
  spectator_state: spectatorState,
  round_reveal: reveal,
  match_result: matchResult,
  spectator_count: (v) => number(v.count),
  rematch_requested: (v) => string(v.match_id),
  error: (v) => string(v.message),
};

/** Validate the app-owned realtime union at the untrusted WebSocket boundary. */
export function parseServerEvent(value: unknown): ServerEvent | undefined {
  if (!record(value) || !string(value.type) || !parsers[value.type]?.(value)) return undefined;
  return value as unknown as ServerEvent;
}

export interface LedgerEntry {
  round: number;
  mine: string;
  theirs: string;
  result: string;
}
