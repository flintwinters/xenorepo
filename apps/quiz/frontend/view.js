import { html } from "lit";

export const view = html`<main class="inventory" aria-label="Working Style Inventory">
  <header class="utility">
    <span class="brand">◈ WORKING STYLE</span><span class="context">SELF-REFLECTION / EIGHT ITEMS</span
    ><span class="live" id="live">READY</span><button id="restart">RESTART</button>
  </header>
  <section class="grid">
    <aside class="pane bank">
      <h2 class="pane-title">ITEMS</h2>
      <ol class="item-list" id="itemList"></ol>
    </aside>
    <section class="pane arena">
      <h2 class="pane-title">RESPONSE</h2>
      <div class="question-area">
        <div class="progress"><span id="position">ITEM 1 / 8</span><span id="dimension">FOCUS</span></div>
        <h1 class="prompt" id="prompt"></h1>
        <div class="answers" id="answers" aria-live="polite"></div>
      </div>
    </section>
    <aside class="pane profile">
      <h2 class="pane-title">PROFILE</h2>
      <div class="profile-card">
        <dl>
          <dt>FOCUS</dt>
          <dd id="focus">—</dd>
          <dt>STRUCTURE</dt>
          <dd id="structure">—</dd>
          <dt>CONNECTION</dt>
          <dd id="connection">—</dd>
          <dt>ADAPTABILITY</dt>
          <dd id="adaptability">—</dd>
        </dl>
        <div class="meter"><i id="meter"></i></div>
        <div class="status-message" id="message">
          <strong>There are no right answers.</strong>Choose the response that fits you best.
        </div>
      </div>
    </aside>
    <section class="pane review">
      <h2 class="pane-title">RESPONSE LOG</h2>
      <div class="pane-body">
        <ol class="review-list" id="review">
          <li>
            <span class="muted">—</span><span class="muted">Your responses will appear here.</span
            ><span class="result">WAITING</span>
          </li>
        </ol>
      </div>
    </section>
  </section>
  <footer class="status">
    <span><strong>● PRIVATE LOCAL SESSION</strong> · NOT A CLINICAL ASSESSMENT</span
    ><span class="hint">1–5 SELECT · ENTER CONTINUE · R RESTART</span><span id="completion">0 RECORDED</span>
  </footer>
</main>`;
