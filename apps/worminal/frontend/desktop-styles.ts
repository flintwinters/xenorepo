import xtermCss from "@xterm/xterm/css/xterm.css";
import { css, unsafeCSS } from "lit";

import { TERMINAL_ROW_HEIGHT } from "./styles.js";

export const desktopStyles = [
  unsafeCSS(xtermCss),
  css`
    :host {
      display: block;
      height: 100%;
      color: #ebdbb2;
      font:
        11px/1.15 "Courier New",
        monospace;
      background: #1d2021;
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
      letter-spacing: 0.1em;
    }
    .push {
      margin-left: auto;
    }
    .desktop {
      position: relative;
      min-width: 0;
      min-height: 0;
      overflow: hidden;
      background-color: #1a1d1c;
      background-image:
        linear-gradient(#282b2a 1px, transparent 1px), linear-gradient(90deg, #282b2a 1px, transparent 1px);
      background-size: 24px 24px;
    }
    .welcome {
      position: absolute;
      inset: 0;
      display: grid;
      place-content: center;
      gap: 10px;
      text-align: center;
      color: #a89984;
      pointer-events: none;
    }
    .welcome strong {
      color: #ebdbb2;
      font-size: 18px;
    }
    .window {
      position: absolute;
      display: grid;
      grid-template-rows: 20px minmax(0, 1fr);
      min-width: 300px;
      min-height: 190px;
      overflow: hidden;
      background: #181a1b;
      border: 1px solid #111;
      box-shadow: 5px 7px 18px #0009;
      resize: both;
    }
    .window.active {
      border-color: #83a598;
      box-shadow:
        5px 7px 22px #000c,
        0 0 0 1px #83a598;
    }
    .window.maximized {
      inset: 0 !important;
      width: 100% !important;
      height: 100% !important;
      resize: none;
    }
    .titlebar {
      display: flex;
      align-items: stretch;
      min-width: 0;
      color: #1d2021;
      font-weight: bold;
      background: linear-gradient(#83a598, #5f7f75);
      border-top: 1px solid #b7cfca;
      border-bottom: 2px solid #354a44;
      cursor: move;
      user-select: none;
      touch-action: none;
    }
    .window:not(.active) .titlebar {
      filter: saturate(0.35) brightness(0.72);
    }
    .tabs {
      display: flex;
      min-width: 0;
      overflow: hidden;
    }
    .tab {
      display: flex;
      align-items: center;
      gap: 5px;
      min-width: 72px;
      max-width: 180px;
      padding: 0 5px;
      opacity: 0.68;
      border-right: 1px solid #354a44;
      cursor: grab;
    }
    .tab.active {
      opacity: 1;
      background: #b7cfca55;
    }
    .tab-title {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .tab-close {
      width: auto !important;
      padding: 0 2px !important;
      color: #282828 !important;
      background: transparent !important;
      border: 0 !important;
    }
    .new-tab {
      width: 24px;
      color: #282828 !important;
      background: transparent !important;
      border: 0 !important;
    }
    .phase {
      color: #282828;
      font-weight: normal;
    }
    .controls {
      display: flex;
      align-self: stretch;
      margin-left: auto;
    }
    .titlebar button {
      width: 24px;
      padding: 0;
      color: #ebdbb2;
      font: inherit;
      background: #35312f;
      border: 1px solid #928374;
      cursor: pointer;
    }
    .titlebar button:hover {
      background: #45413f;
      border-color: #c6b58f;
    }
    .titlebar button:active {
      background: #181716;
    }
    .terminal-stack {
      position: relative;
      min-width: 0;
      min-height: 0;
    }
    .terminal-host {
      position: absolute;
      inset: 0;
      min-width: 0;
      min-height: 0;
      padding: 5px;
      overflow: hidden;
      background: #181a1b;
    }
    .terminal-host:not(.active) {
      visibility: hidden;
      pointer-events: none;
    }
    .terminal-host .xterm {
      height: 100%;
    }
    .terminal-host .xterm-viewport {
      scrollbar-color: #665c54 #181a1b;
    }
    .terminal-host .xterm-rows > div {
      height: ${TERMINAL_ROW_HEIGHT}px !important;
      line-height: ${TERMINAL_ROW_HEIGHT}px !important;
      overflow: visible !important;
    }
    .taskbar {
      display: flex;
      align-items: center;
      gap: 4px;
      min-width: 0;
      overflow-x: auto;
    }
    .task {
      min-width: 95px;
      max-width: 170px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .task.active {
      color: #fabd2f;
    }
    .settings {
      position: fixed;
      inset: 0;
      z-index: 200000;
      display: grid;
      place-items: center;
      padding: 18px;
      background: #000a;
    }
    .settings-panel {
      width: min(440px, 100%);
      padding: 16px;
      color: #ebdbb2;
      background: #282828;
      border: 1px solid #83a598;
      box-shadow: 8px 10px 30px #000;
    }
    .settings-panel h2 {
      margin: 0 0 8px;
      color: #fabd2f;
      font-size: 15px;
      letter-spacing: 0.08em;
    }
    .settings-panel p {
      margin: 0 0 14px;
      color: #a89984;
    }
    .shortcut-row {
      display: grid;
      grid-template-columns: 1fr minmax(160px, 1fr);
      gap: 10px;
      align-items: center;
      padding: 10px 0;
      border-top: 1px solid #504945;
    }
    .shortcut-row input {
      width: 100%;
      padding: 7px;
      color: #ebdbb2;
      font: inherit;
      background: #1d2021;
      border: 1px solid #665c54;
    }
    .shortcut-row input:focus {
      outline: 1px solid #fabd2f;
      border-color: #fabd2f;
    }
    .password-settings {
      display: grid;
      gap: 8px;
      padding-top: 12px;
      border-top: 1px solid #504945;
    }
    .password-settings h3 {
      margin: 0 0 2px;
      color: #83a598;
      font-size: 12px;
      letter-spacing: 0.06em;
    }
    .password-settings label {
      display: grid;
      grid-template-columns: 1fr minmax(160px, 1fr);
      gap: 10px;
      align-items: center;
    }
    .password-settings input {
      width: 100%;
      padding: 7px;
      color: #ebdbb2;
      font: inherit;
      background: #1d2021;
      border: 1px solid #665c54;
    }
    .password-settings input:focus {
      outline: 1px solid #fabd2f;
      border-color: #fabd2f;
    }
    .settings-error {
      min-height: 15px;
      color: #fb4934;
    }
    .settings-actions {
      display: flex;
      justify-content: flex-end;
      gap: 7px;
      margin-top: 14px;
    }
    @media (max-width: 620px) {
      .optional {
        display: none;
      }
      .window {
        min-width: 260px;
      }
    }
  `,
];
