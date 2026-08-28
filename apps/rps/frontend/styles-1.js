export const styles1 = String.raw`:root {
        color-scheme: dark;
        --bg: #1d2021;
        --panel: #282828;
        --well: #181a1b;
        --line: #504945;
        --fg: #ebdbb2;
        --muted: #a89984;
        --red: #fb4934;
        --green: #b8bb26;
        --yellow: #fabd2f;
        --blue: #83a598;
        --purple: #d3869b;
        --aqua: #8ec07c;
        --orange: #fe8019;
        font:
          12px/1.3 "Courier New",
          monospace;
      }
      * {
        box-sizing: border-box;
      }
      html,
      body {
        height: 100%;
        margin: 0;
        overflow: hidden;
        background: var(--bg);
        color: var(--fg);
      }
      button,
      input {
        font: inherit;
        color: inherit;
      }
      .key {
        min-height: 20px;
        padding: 1px 8px;
        color: var(--fg);
        background: linear-gradient(#45413f, #302d2b);
        border: 1px solid #a89984;
        box-shadow:
          inset 0 1px rgb(255 255 255/0.12),
          inset 0 -1px #1d2021,
          0 2px 2px #101112;
        cursor: pointer;
      }
      .key:hover:not(:disabled) {
        background: linear-gradient(#504b48, #383431);
        border-color: #d5c4a1;
      }
      .key:active {
        transform: translateY(1px);
        background: linear-gradient(#242220, #181716);
        box-shadow: inset 0 3px 3px #0e0f0f;
      }
      .key:disabled {
        color: #665c54;
        cursor: not-allowed;
      }
      .key:focus-visible,
      input:focus-visible {
        outline: 2px solid var(--yellow);
        outline-offset: 1px;
      }
      .landing {
        height: 100%;
        display: grid;
        grid-template-rows: 22px minmax(0, 1fr) 20px;
        border: 1px solid #0d0e0e;
        background: #111;
      }
      [hidden] {
        display: none !important;
      }
      .landing-utility,
      .landing-status {
        display: flex;
        align-items: center;
        gap: 7px;
        min-width: 0;
        padding: 1px 6px;
        background: linear-gradient(#3c3836, #282828);
        border-top: 1px solid #504945;
        border-bottom: 1px solid #101112;
        white-space: nowrap;
      }
      .landing-status {
        justify-content: space-between;
        color: var(--muted);
      }
      .landing-mosaic {
        min-height: 0;
        display: grid;
        grid-template-columns: minmax(260px, 2fr) minmax(280px, 1fr);
        gap: 1px;
      }
      .entry-body {
        display: grid;
        place-items: center;
        align-content: center;
        gap: 18px;
        padding: 18px;
      }
      .mark {
        color: var(--yellow);
        font-size: 18px;
        font-weight: bold;
        letter-spacing: 0.12em;
      }
      .play-form {
        width: min(390px, 100%);
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: end;
        gap: 7px;
      }
      .play-form label {
        display: grid;
        gap: 3px;
        color: var(--muted);
      }
      input {
        width: 100%;
        height: 22px;
        padding: 2px 6px;
        background: var(--well);
        border: 1px solid #111;
        border-right-color: var(--line);
        border-bottom-color: var(--line);
      }
      .play {
        min-width: 104px;
        height: 42px;
        font-size: 18px;
        font-weight: bold;
      }
      .landing-live {
        min-height: 0;
      }
      .landing-live .pane-body {
        background: var(--well);
      }
      .landing-stats {
        display: flex;
        gap: 14px;
        margin-left: auto;
        color: var(--muted);
      }
      .landing-stats strong {
        color: var(--aqua);
      }
      .public-title {
        padding: 7px;
        color: var(--yellow);
        border-top: 1px solid var(--line);
      }
      .public-list {
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .public-list li {
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: center;
        gap: 8px;
        padding: 7px;
        border-top: 1px solid var(--line);
      }
      .match-player {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        color: var(--aqua);
      }
      .match-player span:last-child {
        color: var(--yellow);
      }
      .match-meta,
      .activity {
        color: var(--muted);
        font-size: 10px;
      }
      .activity {
        padding: 6px;
        border-bottom: 1px solid var(--line);
      }
      .message {
        padding: 5px 7px;
        color: var(--muted);
        border-top: 1px solid var(--line);
      }
      .message.error {
        color: var(--red);
      }
      .frame {
        height: 100%;
        display: grid;
        grid-template-rows: 22px 1fr;
        background: #111;
      }
      .utility {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 1px 6px;
        background: #32302f;
      }
      .utility .key {
        min-height: 18px;
        padding: 1px 6px;
      }
      .brand {
        color: var(--yellow);
        font-weight: bold;
        letter-spacing: 0.08em;
      }
      .utility .key {
        margin-left: auto;
      }
      .link {
        color: var(--green);
      }
      .link.offline {
        color: var(--red);
      }
      .mosaic {
        min-height: 0;
        display: grid;
        grid-template-columns: 190px 1fr;
        grid-template-rows: 1fr 164px;
        gap: 1px;
      }
      .pane {
        min-height: 0;
        display: grid;
        grid-template-rows: 18px 1fr;
        overflow: hidden;
        background: var(--panel);
      }
      .pane-title {
        position: relative;
        z-index: 1;
        display: flex;
        align-items: center;
        gap: 5px;
        margin: 0;
        padding-right: 5px;
        color: #1d2021;
        font-size: 12px;
        line-height: 1;
        background: linear-gradient(to bottom, #aec7c2 0 1px, #83a598 1px calc(100% - 2px), #3e625e calc(100% - 2px));
        box-shadow:
          inset 0 1px rgb(255 255 255/0.12),
          inset 0 -1px rgb(0 0 0/0.25),
          0 2px 2px #111;
      }
      .green {
        background: linear-gradient(to bottom, #d1d36c 0 1px, #b8bb26 1px calc(100% - 2px), #66680f calc(100% - 2px));
      }
      .purple {
        background: linear-gradient(to bottom, #e8b2c0 0 1px, #d3869b 1px calc(100% - 2px), #70405a calc(100% - 2px));
      }
      .title-meta {
        margin-left: auto;
      }
      .pane-body {
        overflow: auto;
      }
      .arena-index {
        grid-row: 1/3;
      }
      .battle,
      .ledger {
        grid-column: 2;
      }
      .ledger {
        grid-row: 2;
      }
      .metrics {
        display: grid;
        grid-template-columns: 1fr auto;
        margin: 0;
      }
      .metrics dt,
      .metrics dd {
        margin: 0;
        padding: 5px;
        border-bottom: 1px solid var(--line);
      }
      .metrics dt {
        color: var(--muted);
      }
      .metrics dd {
        color: var(--aqua);
      }
      .battle-body {
        height: 100%;
        display: grid;
        grid-template-rows: 42px 1fr auto 24px 42px;
      }
      .player-strip {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 9px;
      }
      .opponent {
        border-bottom: 1px solid var(--line);
      }
      .you {
        border-top: 1px solid var(--line);
        background: #32302f;
      }
      .label {
        color: var(--muted);
      }
      .name {
        color: var(--aqua);
        font-size: 14px;
        font-weight: bold;
      }
      .streak {
        color: var(--yellow);
      }
      .instrument {
        display: grid;
        grid-template-columns: 82px 1fr;
        min-height: 0;
        background: var(--well);
      }
      .timer,
      .standby {
        display: grid;
        place-items: center;
        align-content: center;
      }
      .timer {
        border-right: 1px solid var(--line);
      }
      .clock {
        color: var(--yellow);
        font-size: 34px;
      }
      .clock.low {
        color: var(--red);
      }
      .round {
        color: var(--muted);
      }
      .result {
        display: grid;
        grid-template-columns: 1fr 76px 1fr;
        align-items: center;
        text-align: center;
      }
      .pick {
        color: var(--orange);
        font-size: 24px;
      }
      .outcome {
        color: var(--yellow);
      }
      .throws {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 5px;
        padding: 7px;
      }
      .throw {
        display: grid;
        grid-template-columns: 20px 1fr auto;
        align-items: center;
        text-align: left;
      }
      .throw.selected {
        color: var(--aqua);
      }
      .shortcut {
        color: var(--muted);
        font-size: 10px;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
      }
      th,
      td {
        height: 24px;
        padding: 3px 7px;
        border: 1px solid var(--line);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      th {
        position: sticky;
        top: 0;
        background: #32302f;
        color: var(--muted);
        font-weight: normal;
      }
      .empty td {
        text-align: center;
        color: var(--muted);
      }
      .frame {
        --signal: #665c54;
        box-shadow: inset 0 0 0 7px var(--signal);
      }
      .signal-idle {
        --signal: #665c54;
      }
      .signal-search {
        --signal: var(--yellow);
      }
      .signal-active {
        --signal: var(--aqua);
      }
      .signal-locked {
        --signal: var(--blue);
      }`;
