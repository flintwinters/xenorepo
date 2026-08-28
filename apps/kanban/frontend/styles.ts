/** App-owned visual contract for the durable board. */
import { css } from "lit";

export const kanbanStyles = css`
      :host {
        display: block;
        height: 100%;
        color: #ebdbb2;
        font:
          12px/1.3 "Courier New",
          monospace;
      }
      * {
        box-sizing: border-box;
      }
      x-console-shell {
        height: 100%;
      }
      .brand {
        color: #fabd2f;
        font-weight: bold;
        letter-spacing: 0.08em;
      }
      .push {
        margin-left: auto;
      }
      .board {
        min-height: 0;
        display: grid;
        grid-template-columns: repeat(3, minmax(220px, 1fr));
        gap: 1px;
        background: #121414;
      }
      x-console-pane {
        min-width: 0;
      }
      .column {
        display: grid;
        min-height: 100%;
        grid-template-rows: auto minmax(0, 1fr);
      }
      .count {
        margin-left: auto;
        color: #1d2021;
        font-weight: normal;
      }
      .add-form {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        border-bottom: 1px solid #504945;
      }
      .add-form label {
        position: absolute;
        width: 1px;
        height: 1px;
        overflow: hidden;
        clip: rect(0 0 0 0);
      }
      input,
      textarea {
        min-width: 0;
        padding: 3px 6px;
        color: #ebdbb2;
        font: inherit;
        background: #181a1b;
        border: 1px solid #665c54;
      }
      .cards {
        min-height: 0;
        overflow: auto;
      }
      .cards.drop-target {
        background: #30312d;
        box-shadow: inset 0 0 0 1px #d79921;
      }
      .card {
        position: relative;
        min-height: 34px;
        padding: 8px 30px 7px 50px;
        border-bottom: 1px solid #504945;
        border-left: 2px solid #928374;
        background: #222526;
        cursor: grab;
        user-select: none;
      }
      .card.needs-review {
        border-left-color: #fabd2f;
        background: #3b321f;
        box-shadow: inset 3px 0 #d79921;
      }
      .review {
        position: absolute;
        top: 8px;
        left: 28px;
        margin: 0;
        accent-color: #b8bb26;
        cursor: pointer;
      }
      .card.dragging {
        opacity: 0.42;
      }
      .card.insert-before {
        box-shadow: inset 0 2px #fabd2f;
      }
      .card.insert-after {
        box-shadow: inset 0 -2px #fabd2f;
      }
      .drag-handle {
        position: absolute;
        inset: 0 auto 0 0;
        width: 24px;
        padding: 0;
        color: #a89984;
        font: inherit;
        background: transparent;
        border: 0;
        cursor: grab;
        touch-action: none;
        user-select: none;
      }
      .drag-handle:hover,
      .drag-handle:focus-visible {
        color: #fabd2f;
        background: #3c3836;
        outline: 1px solid #fabd2f;
        outline-offset: -1px;
      }
      .drag-handle:active,
      .card.dragging {
        cursor: grabbing;
      }
      .card-title {
        margin: 0;
        overflow-wrap: anywhere;
      }
      .delete {
        position: absolute;
        top: 3px;
        right: 3px;
      }
      .delete::part(button) {
        min-width: 20px;
        padding: 0;
        color: #fb8b7d;
      }
      .modal-backdrop {
        position: fixed;
        z-index: 10;
        inset: 0;
        display: grid;
        place-items: center;
        padding: 16px;
        background: #000a;
      }
      .modal {
        width: min(560px, 100%);
        max-height: min(700px, calc(100vh - 32px));
        overflow: auto;
        padding: 14px;
        border: 1px solid #83a598;
        background: #282828;
        box-shadow: 0 12px 30px #000;
      }
      .modal h2 {
        margin: 0 0 10px;
        font-size: 13px;
      }
      .edit-form {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto auto;
        gap: 5px;
      }
      .log-heading {
        margin: 18px 0 6px;
        color: #83a598;
        font-size: 12px;
        letter-spacing: 0.06em;
      }
      .note-log {
        display: grid;
        gap: 1px;
        margin: 0 0 6px;
        padding: 0;
        list-style: none;
        background: #504945;
      }
      .note {
        display: grid;
        gap: 3px;
        padding: 7px;
        background: #1d2021;
      }
      .note time {
        color: #a89984;
        font-size: 10px;
      }
      .note p {
        margin: 0;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
      .note-form {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 5px;
        align-items: end;
      }
      .note-form textarea {
        min-height: 54px;
      }
      .error {
        color: #fb4934;
      }
      @media (max-width: 720px) {
        .board {
          grid-template-columns: 1fr;
          overflow: auto;
        }
        x-console-pane {
          min-height: 220px;
        }
        .context {
          display: none;
        }
      }
  `;
