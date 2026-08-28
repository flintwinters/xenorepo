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

/** Recessed form controls and contained overlays shared by Lit applications. */
export const consoleControls = css`
  input, textarea, select { font: inherit; }
  textarea {
    border-radius: 3px;
  }
  input[type="checkbox"] {
    appearance: none;
    display: inline-grid;
    flex: 0 0 auto;
    width: 14px;
    height: 14px;
    margin: 0;
    padding: 2px;
    place-content: center;
    color: var(--console-ink, #1d2021);
    background: var(--console-well, #181a1b);
    border: 1px solid var(--console-line, #665c54);
    border-radius: 2px;
    box-shadow: inset 0 1px 2px rgb(0 0 0 / 0.65);
    cursor: pointer;
  }
  input[type="checkbox"]::before {
    width: 8px;
    height: 8px;
    content: "";
    background: var(--console-accent, #b8bb26);
    box-shadow: inset 0 1px rgb(255 255 255 / 0.22), 0 0 2px rgb(184 187 38 / 0.35);
    transform: scale(0);
  }
  input[type="checkbox"]:checked::before { transform: scale(1); }
  input[type="checkbox"]:disabled { cursor: not-allowed; opacity: 0.6; }
  [role="dialog"] { border-radius: 4px; }
`;

export const chrome = css`
  :host { display: block; min-width: 0; }
  .chrome {
    display: flex; align-items: center; gap: 5px; min-height: 18px; padding-inline: 5px;
    color: var(--console-ink, #1d2021); font-weight: bold;
    background: linear-gradient(var(--console-tone-light, #83a598), var(--console-tone-dark, #5f7f75));
    border-top: 1px solid var(--console-tone-rim, #b7cfca);
    border-bottom: 2px solid var(--console-tone-shadow, #354a44);
    box-shadow: 0 2px 2px #111;
  }
`;
