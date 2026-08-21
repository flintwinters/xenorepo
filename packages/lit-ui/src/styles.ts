import { css } from "lit";

/** Shared tokens only; consuming pages set these on their document root. */
export const consoleTokens = css`
  :host {
    color: var(--console-fg, #ebdbb2);
    font: var(--console-font, 12px/1.3 "Courier New", monospace);
  }
  *, *::before, *::after { box-sizing: border-box; }
  button, input { font: inherit; }
  :focus-visible { outline: 2px solid var(--console-focus, #fabd2f); outline-offset: 2px; }
`;

export const chrome = css`
  :host { display: block; min-width: 0; }
  .chrome {
    display: flex; align-items: center; gap: 5px; min-height: 18px;
    color: var(--console-ink, #1d2021); font-weight: bold;
    background: linear-gradient(var(--console-tone-light, #83a598), var(--console-tone-dark, #5f7f75));
    border-top: 1px solid var(--console-tone-rim, #b7cfca);
    border-bottom: 2px solid var(--console-tone-shadow, #354a44);
    box-shadow: 0 2px 2px #111;
  }
`;
