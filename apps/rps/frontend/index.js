import { render } from "lit";
import { styles1 } from "./styles-1.js";
import { styles2 } from "./styles-2.js";
import { view } from "./view.js";

function start() {
  (() => {
    "use strict";
    const $ = (id) => document.getElementById(id),
      buttons = [...document.querySelectorAll("[data-throw]")],
      icons = { rock: "🪨", paper: "📄", scissors: "✂️" };
    let socket,
      player = {},
      mode = "idle",
      submitted = false,
      ties = 0,
      timer,
      rounds = [],
      watched = null,
      completedMatchId = null,
      rematchRequested = false;
    const text = (id, v) => ($(id).textContent = v ?? "——");
    function replay(node, name) {
      node.classList.remove(name);
      void node.offsetWidth;
      node.classList.add(name);
    }
    function showArena() {
      $("landing").hidden = true;
      $("arena-view").hidden = false;
    }
    function announce(v, tone = "active") {
      text("message", v);
      $("message").className = "message";
      replay($("message"), "message-announce");
      $("arena-view").className = `frame signal-${tone}`;
    }
    function fail(v) {
      if ($("landing").hidden) announce(v, "error");
      else {
        text("landing-message", v);
        $("landing-message").classList.add("error");
      }
    }
    function send(type, data = {}) {
      if (socket?.readyState !== 1) return fail("CONNECTION LOST");
      socket.send(JSON.stringify({ type, client_id: crypto.randomUUID(), ...data }));
    }
    function controls() {
      buttons.forEach((b) => (b.disabled = mode !== "match" || submitted));
      $("queue").disabled = socket?.readyState !== 1 || mode === "match" || mode === "spectating";
      text("queue", mode === "queued" ? "LEAVE QUEUE" : "JOIN QUEUE");
      const rematch = $("rematch"),
        available = mode === "complete" && !watched && completedMatchId;
      rematch.hidden = !available;
      rematch.disabled = !available || rematchRequested || socket?.readyState !== 1;
    }
    function matchList(node, matches) {
      node.replaceChildren();
      if (!matches.length) {
        const li = document.createElement("li");
        li.textContent = "NO ACTIVE MATCHES";
        node.append(li);
      }
      matches.forEach((match) => {
        const li = document.createElement("li"),
          players = document.createElement("div"),
          watch = document.createElement("button");
        match.participants.forEach((p) => {
          const row = document.createElement("div");
          row.className = "match-player";
          const name = document.createElement("span"),
            streak = document.createElement("span");
          name.textContent = p.nickname;
          streak.textContent = `STREAK ${p.competitive_streak}`;
          row.append(name, streak);
          players.append(row);
        });
        const meta = document.createElement("div");
        meta.className = "match-meta";
        meta.textContent = `${match.ranked ? "RANKED" : "UNRANKED"} · ${match.spectator_count} VIEWING`;
        players.append(meta);
        watch.className = "key";
        watch.dataset.watch = match.match_id;
        watch.textContent = "WATCH";
        li.append(players, watch);
        node.append(li);
      });
    }
    function arena(d) {
      [
        ["online", d.visitors],
        ["queue-size", d.queue_size],
        ["active-count", d.active_matches],
        ["landing-online", d.visitors],
        ["landing-active", d.active_matches],
      ].forEach((x) => text(...x));
      matchList($("top-matches"), d.top_matches);
      matchList($("landing-matches"), d.top_matches);
      const recent = $("recent-results");
      recent.replaceChildren();
      d.recent_results.forEach((r) => {
        const e = document.createElement("div"),
          winner = r.participants.find((p) => p.id === r.winner_id);
        e.className = "activity";
        e.textContent = `${r.outcome.toUpperCase()} · ${winner?.nickname || "DRAW"}`;
        recent.append(e);
      });
    }
    function clock(deadline) {
      clearInterval(timer);
      const end = Date.parse(deadline),
        tick = () => {
          const n = Math.max(0, Math.ceil((end - Date.now()) / 1000));
          text("clock", n);
          $("clock").classList.toggle("low", n <= 3);
          if (!n) clearInterval(timer);
        };
      tick();
      timer = setInterval(tick, 200);
    }
    function renderLedger() {
      const body = $("round-log");
      body.replaceChildren();
      if (!rounds.length) {
        const row = body.insertRow(),
          cell = row.insertCell();
        row.className = "empty";
        cell.colSpan = 5;
        cell.textContent = "NO RESOLVED ROUNDS";
      }
      rounds.forEach((e, i) => {
        const row = body.insertRow();
        [rounds.length - i, e.round, e.mine, e.theirs, e.result].forEach((v) => (row.insertCell().textContent = v));
      });
      text("ledger-count", `${rounds.length} ENTRIES`);
    }
    function spectator(d) {
      showArena();
      mode = "spectating";
      submitted = true;
      watched = d.match_id;
      $("standby").classList.remove("searching");
      const [a, b] = d.participants;
      text("opponent-label", "PLAYER A");
      text("you-label", "PLAYER B");
      text("your-name", a.nickname);
      text("your-streak", a.competitive_streak);
      text("opponent", b.nickname);
      text("opponent-streak", b.competitive_streak);
      text("round", `ROUND ${d.round}`);
      text("ties", `TIES ${d.tie_count} / 5`);
      announce(`WATCHING ${a.nickname} VS ${b.nickname} · ${d.spectator_count} VIEWING`);
      rounds = d.revealed_rounds
        .map((e) => {
          const v = Object.values(e.throws);
          return {
            round: e.round,
            mine: v[0].toUpperCase(),
            theirs: v[1].toUpperCase(),
            result: e.outcome.toUpperCase(),
          };
        })
        .reverse();
      renderLedger();
      clock(d.deadline);
      controls();
    }
    function match(d) {
      showArena();
      mode = "match";
      watched = null;
      ties = 0;
      rounds = [];
      renderLedger();
      buttons.forEach((b) => b.classList.remove("selected"));
      $("result").hidden = true;
      $("standby").hidden = false;
      $("standby").classList.remove("searching");
      text("opponent-label", "OPPONENT");
      text("you-label", "YOU");
      text("opponent", d.opponent.nickname);
      text("opponent-streak", d.opponent.competitive_streak);
      text("standby", `MATCH START · ${player.nickname} VS ${d.opponent.nickname}`);
      announce(`MATCH START · YOU VS ${d.opponent.nickname}`);
      controls();
    }
    function round(d) {
      showArena();
      mode = "match";
      submitted = d.submitted;
      buttons.forEach((b) => b.classList.remove("selected"));
      $("result").hidden = true;
      $("standby").hidden = false;
      $("standby").classList.remove("searching");
      text("round", `ROUND ${d.round}`);
      $("opponent-strip").classList.toggle("ready", d.opponent_submitted);
      $("you-strip").classList.toggle("ready", submitted);
      const state = submitted
          ? "YOUR THROW LOCKED · WAITING FOR OPPONENT"
          : d.opponent_submitted
            ? "OPPONENT READY · YOUR THROW"
            : d.round === 1
              ? "MATCH START · CHOOSE YOUR THROW"
              : `ROUND ${d.round} OPEN · LAST ${rounds[0]?.result || "TIE"}`,
        tone = submitted ? "locked" : d.opponent_submitted ? "ready" : "active";
      text("standby", state);
      announce(state, tone);
      clock(d.deadline);
      controls();
    }
    function revealSelections(d) {
      const values = Object.values(d.throws),
        mine = d.throws[player.id] || values[0];
      if (!d.throws[player.id]) return [mine, values[1]];
      return [mine, Object.entries(d.throws).find(([id]) => id !== player.id)[1]];
    }
    function revealResult(d) {
      if (d.outcome === "tie") return "TIE";
      if (watched) return "DECISIVE";
      return d.winner_id === player.id ? "WIN" : "LOSS";
    }
    function resultTone(result) {
      if (result === "WIN") return "win";
      if (result === "LOSS") return "loss";
      return "tie";
    }
    function reveal(d) {
      clearInterval(timer);
      submitted = true;
      const [mine, theirs] = revealSelections(d),
        result = revealResult(d),
        resultNode = $("result"),
        resultClass = `result-${resultTone(result)}`;
      text("your-pick", icons[mine]);
      text("their-pick", icons[theirs]);
      text("outcome", result);
      $("standby").hidden = true;
      resultNode.hidden = false;
      resultNode.classList.remove("result-win", "result-loss", "result-tie", "result-finish");
      resultNode.classList.add(resultClass);
      replay(resultNode, "result-reveal");
      if (d.outcome === "tie") ties++;
      text("ties", `TIES ${ties} / 5`);
      rounds.unshift({ round: d.round, mine: mine.toUpperCase(), theirs: theirs.toUpperCase(), result });
      renderLedger();
      announce(`ROUND ${d.round} · ${result}`, resultTone(result));
    }
    function finishLabel(d, winner, won) {
      if (d.outcome === "draw") return "MATCH DRAW";
      if (watched) return `${winner?.nickname || "PLAYER"} WINS`;
      return won ? "MATCH WON" : "MATCH LOST";
    }
    function finishTone(d, won) {
      if (d.outcome === "draw") return "tie";
      return watched || won ? "win" : "loss";
    }
    function finish(d) {
      mode = "complete";
      completedMatchId = d.id || null;
      rematchRequested = false;
      clearInterval(timer);
      submitted = true;
      $("opponent-strip").classList.remove("ready");
      $("you-strip").classList.remove("ready");
      if (d.player) playerView(d.player);
      text("round", "FINAL");
      const winner = d.participants?.find((p) => p.id === d.winner_id),
        won = d.winner_id === player.id,
        label = finishLabel(d, winner, won),
        tone = finishTone(d, won);
      replay($("result"), "result-finish");
      announce(watched ? label : `${label} · REQUEUING`, tone);
    }
    function queueState(d) {
      mode = d.queued ? "queued" : "idle";
      showArena();
      $("standby").classList.toggle("searching", d.queued);
      text("standby", d.queued ? "SEARCHING FOR OPPONENT" : "READY TO JOIN QUEUE");
      announce(d.queued ? "MATCHMAKING · SEARCHING FOR OPPONENT" : "QUEUE LEFT · READY", d.queued ? "search" : "idle");
    }
    function rematchRequestedView() {
      rematchRequested = true;
      announce("REMATCH REQUESTED", "ready");
    }
    function spectatorCount(d) {
      announce(`SPECTATING · ${d.count} VIEWING`);
    }
    function playerView(p) {
      player = p;
      text("your-name", p.nickname);
      text("your-streak", p.competitive_streak || 0);
      if ($("landing").hidden) $("nickname").value = p.nickname;
    }
    function apply(d) {
      const handlers = {
          session: (x) => playerView(x.player),
          arena_snapshot: arena,
          queue_state: queueState,
          match_assignment: match,
          round_state: round,
          spectator_state: spectator,
          spectator_count: spectatorCount,
          round_reveal: reveal,
          match_result: finish,
          rematch_requested: rematchRequestedView,
          error: (x) => fail(x.message),
        },
        handler = handlers[d.type];
      if (handler) handler(d);
      controls();
    }
    async function request(path, opt) {
      const r = await fetch(path, opt),
        body = await r.json();
      if (!r.ok) {
        const error = Error(body.error || "REQUEST FAILED");
        error.status = r.status;
        throw error;
      }
      return body;
    }
    async function connect() {
      try {
        playerView(await request("/api/session"));
        socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
        socket.onopen = () => {
          $("link").classList.remove("offline");
          text("link", "● ONLINE");
          text("landing-message", "READY");
          syncPlay();
          controls();
        };
        socket.onmessage = (e) => {
          try {
            apply(JSON.parse(e.data));
          } catch {
            fail("INVALID SERVER MESSAGE");
          }
        };
        socket.onclose = () => {
          text("link", "● RECONNECTING");
          if ($("landing").hidden) announce("CONNECTION LOST · RECONNECTING", "error");
          syncPlay();
          setTimeout(connect, 2000);
        };
      } catch (e) {
        fail(e.message);
        if (e.status === 404) {
          text("link", "● WRONG SERVICE");
          return;
        }
        setTimeout(connect, 2000);
      }
    }
    const syncPlay = () => ($("play").disabled = socket?.readyState !== 1 || !$("play-form").checkValidity());
    $("nickname").oninput = syncPlay;
    $("play-form").onsubmit = async (e) => {
      e.preventDefault();
      try {
        playerView(
          await request("/api/session", {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nickname: $("nickname").value }),
          }),
        );
        showArena();
        mode = "queued";
        controls();
        send("queue_join");
      } catch (error) {
        fail(error.message);
      }
    };
    $("queue").onclick = () => send(mode === "queued" ? "queue_leave" : "queue_join");
    $("rematch").onclick = () => send("rematch", { match_id: completedMatchId });
    function watch(e) {
      const b = e.target.closest("[data-watch]");
      if (b) {
        showArena();
        send("spectate", { match_id: b.dataset.watch });
      }
    }
    $("top-matches").onclick = watch;
    $("landing-matches").onclick = watch;
    buttons.forEach(
      (b) =>
        (b.onclick = () => {
          submitted = true;
          replay(b, "selected");
          announce(`${b.dataset.throw.toUpperCase()} LOCKED · WAITING FOR OPPONENT`, "locked");
          controls();
          send("throw", { selection: b.dataset.throw });
        }),
    );
    document.addEventListener("keydown", (e) => {
      if (e.repeat || e.target.tagName === "INPUT") return;
      const pick = { 1: "rock", r: "rock", 2: "paper", p: "paper", 3: "scissors", s: "scissors" }[e.key.toLowerCase()];
      if (pick) document.querySelector(`[data-throw=${pick}]`).click();
    });
    renderLedger();
    connect();
  })();
}

export function mount(root) {
  if (!root) throw new Error("missing application mount");
  document.title = "Rock Paper Scissors";
  for (const content of [styles1, styles2]) {
    const style = document.createElement("style");
    style.textContent = content;
    document.head.append(style);
  }
  render(view, root);
  start();
}
