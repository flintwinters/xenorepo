import { html } from "lit";

export const view = html`<div class="frame">
  <header class="rail">
    <span class="brand">WIRE/98</span><span class="summary">PUBLIC MICROBLOG CIRCUIT</span
    ><span id="identity">GUEST</span><button class="mobile-account" id="accountCommand">ACCOUNT</button
    ><button id="refresh">REFRESH</button>
  </header>
  <main class="workspace">
    <aside class="pane account" aria-labelledby="account-title">
      <div class="title blue" id="account-title"><span class="plaque">01</span>ACCOUNT LINK</div>
      <div class="account-body">
        <div id="guest">
          <div class="tabs" role="tablist">
            <button class="tab active" id="loginTab" type="button">SIGN IN</button
            ><button class="tab" id="registerTab" type="button">REGISTER</button>
          </div>
          <form id="authForm">
            <label class="field"
              >HANDLE<input
                id="handle"
                autocomplete="username"
                minlength="3"
                maxlength="20"
                pattern="[a-z0-9_]+"
                required /></label
            ><label class="field"
              >PASSWORD<input
                id="password"
                type="password"
                autocomplete="current-password"
                minlength="8"
                maxlength="128"
                required /></label
            ><button id="authSubmit">SIGN IN</button>
          </form>
          <div class="auth-message" id="authMessage" role="alert" aria-live="assertive">ENTER ACCOUNT CREDENTIALS</div>
        </div>
        <div id="signed" class="signed hidden">
          <div>LINK ACTIVE</div>
          <p class="handle" id="signedHandle"></p>
          <button id="logout">SIGN OUT</button>
        </div>
      </div>
    </aside>
    <section class="pane main" aria-labelledby="feed-title">
      <div>
        <div class="title" id="feed-title"><span class="plaque">02</span>TRANSMISSION STREAM</div>
        <form class="composer" id="postForm">
          <label for="body">NEW TRANSMISSION</label
          ><textarea id="body" maxlength="280" placeholder="Sign in to publish." disabled></textarea>
          <div class="compose-row">
            <button id="publish" disabled>PUBLISH</button><span id="composeHint">AUTHENTICATION REQUIRED</span
            ><output class="counter" id="counter">0/280</output>
          </div>
        </form>
      </div>
      <div class="feed" id="feed" aria-live="polite"><div class="empty">SYNCING STREAM…</div></div>
    </section>
  </main>
  <footer class="rail status">
    <span class="signal">● ONLINE</span><span id="message">READY</span><span class="summary"></span
    ><span class="low">LAST SYNC:</span><time id="lastSync">NEVER</time>
  </footer>
</div>`;
