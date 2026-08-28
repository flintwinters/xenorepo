import { html } from "lit";

export const view = html`<section class="landing" id="landing">
    <header class="landing-utility">
      <span class="brand">Rock Paper Scissors</span>
      <div class="landing-stats">
        <span><strong id="landing-online">0</strong> ONLINE</span
        ><span><strong id="landing-active">0</strong> MATCHES</span>
      </div>
    </header>
    <main class="landing-mosaic">
      <section class="pane">
        <h1 class="pane-title green">ENTER ARENA</h1>
        <div class="entry-body">
          <div class="mark">Rock Paper Scissors</div>
          <form class="play-form" id="play-form">
            <label
              >DISPLAY NAME<input id="nickname" minlength="2" maxlength="24" required autocomplete="nickname" /></label
            ><button class="key play" id="play" disabled>PLAY</button>
          </form>
        </div>
      </section>
      <section class="pane landing-live">
        <h2 class="pane-title purple">ONGOING MATCHES</h2>
        <ul class="pane-body public-list" id="landing-matches">
          <li>NO ACTIVE MATCHES</li>
        </ul>
      </section>
    </main>
    <footer class="landing-status">
      <span id="landing-message" role="status">CONNECTING</span><span>THROW/98</span>
    </footer>
  </section>
  <main class="frame signal-idle" id="arena-view" hidden>
    <header class="utility">
      <span class="brand">Rock Paper Scissors</span><button class="key" id="rematch" hidden>REMATCH</button
      ><button class="key" id="queue" disabled>JOIN QUEUE</button><span class="link offline" id="link">● OFFLINE</span>
    </header>
    <section class="mosaic">
      <aside class="pane arena-index">
        <h2 class="pane-title">ARENA</h2>
        <div class="pane-body">
          <dl class="metrics">
            <dt>VISITORS</dt>
            <dd id="online">0</dd>
            <dt>QUEUE</dt>
            <dd id="queue-size">0</dd>
            <dt>ACTIVE</dt>
            <dd id="active-count">0</dd>
          </dl>
          <div class="public-title">TOP MATCHES</div>
          <ul class="public-list" id="top-matches">
            <li>NO ACTIVE MATCHES</li>
          </ul>
          <div class="public-title">RECENT</div>
          <div id="recent-results"><div class="activity">NO RESULTS</div></div>
        </div>
      </aside>
      <section class="pane battle">
        <h1 class="pane-title green">THROW CONTROL <span class="title-meta" id="ties">TIES 0 / 5</span></h1>
        <div class="battle-body">
          <div class="player-strip opponent" id="opponent-strip">
            <div>
              <div class="label" id="opponent-label">OPPONENT</div>
              <div class="name" id="opponent">——</div>
            </div>
            <div class="streak">STREAK <span id="opponent-streak">0</span></div>
          </div>
          <div class="instrument">
            <div class="timer">
              <div class="clock" id="clock">10</div>
              <div class="round" id="round">STANDBY</div>
            </div>
            <div class="standby" id="standby">AWAITING MATCH</div>
            <div class="result" id="result" hidden>
              <div>
                <div class="label">THEIR THROW</div>
                <div class="pick" id="their-pick">?</div>
              </div>
              <div class="outcome" id="outcome">TIE</div>
              <div>
                <div class="label">YOUR THROW</div>
                <div class="pick" id="your-pick">?</div>
              </div>
            </div>
          </div>
          <div class="throws">
            <button class="key throw" data-throw="rock" disabled>
              <span>●</span><span>ROCK</span><span class="shortcut">1 / R</span></button
            ><button class="key throw" data-throw="paper" disabled>
              <span>▰</span><span>PAPER</span><span class="shortcut">2 / P</span></button
            ><button class="key throw" data-throw="scissors" disabled>
              <span>✕</span><span>SCISSORS</span><span class="shortcut">3 / S</span>
            </button>
          </div>
          <div class="message" id="message" role="status">CONNECTING</div>
          <div class="player-strip you" id="you-strip">
            <div>
              <div class="label" id="you-label">YOU</div>
              <div class="name" id="your-name">——</div>
            </div>
            <div class="streak">STREAK <span id="your-streak">0</span></div>
          </div>
        </div>
      </section>
      <section class="pane ledger">
        <h2 class="pane-title purple">ROUNDS <span class="title-meta" id="ledger-count">0 ENTRIES</span></h2>
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
              <tr class="empty">
                <td colspan="5">NO RESOLVED ROUNDS</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>
  </main>`;
