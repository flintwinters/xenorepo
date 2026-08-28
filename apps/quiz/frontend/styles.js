export const styles1 = String.raw`html,
      body {
        overflow: hidden;
      }
      .inventory {
        height: 100vh;
        display: grid;
        grid-template-rows: 22px minmax(0, 1fr) 20px;
      }
      .utility {
        border-top: 1px solid var(--hi);
        padding-block: 1px;
      }
      .utility button {
        min-height: 18px;
        padding: 1px 6px;
      }
      .context,
      .muted {
        color: var(--muted);
      }
      .live {
        margin-left: auto;
        color: var(--aqua);
      }
      .grid {
        min-height: 0;
        display: grid;
        grid-template-columns: 190px minmax(360px, 1fr) 230px;
        grid-template-rows: minmax(300px, 1fr) 155px;
        gap: 1px;
        background: #111;
      }
      .pane {
        display: grid;
        grid-template-rows: 18px minmax(0, 1fr);
      }
      .bank {
        grid-row: 1/3;
      }
      .arena {
        grid-column: 2;
      }
      .profile {
        grid-column: 3;
      }
      .review {
        grid-column: 2/4;
      }
      .pane-title {
        background: linear-gradient(#83a598, #5f7f75);
      }
      .arena .pane-title {
        background: linear-gradient(#b8bb26, #98971a);
        --chrome-rim: #d5d87a;
        --chrome-shade: #57580e;
      }
      .review .pane-title {
        background: linear-gradient(#d3869b, #b16286);
        --chrome-rim: #edb8c5;
        --chrome-shade: #65364c;
      }
      .item-list,
      .review-list {
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .item-list li {
        display: flex;
        gap: 7px;
        padding: 8px;
        border-bottom: 1px solid var(--line);
        color: var(--muted);
      }
      .item-list li.active {
        color: var(--fg);
        background: #32302f;
      }
      .number {
        color: var(--yellow);
        font-weight: bold;
      }
      .question-area {
        height: 100%;
        display: grid;
        grid-template-rows: auto minmax(0, 1fr) auto;
        padding: 16px;
      }
      .progress {
        display: flex;
        justify-content: space-between;
        color: var(--muted);
      }
      .prompt {
        align-self: center;
        max-width: 700px;
        margin: 0;
        color: var(--fg);
        font-size: clamp(20px, 3vw, 34px);
        line-height: 1.15;
      }
      .answers {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 6px;
      }
      .answer {
        min-height: 52px;
        padding: 5px;
        text-align: center;
      }
      .answer .keynum {
        display: block;
        color: var(--yellow);
        font-weight: bold;
      }
      .answer.selected {
        color: var(--green);
        border-color: var(--green);
      }
      .profile-card {
        padding: 10px;
      }
      .profile-card dl {
        display: grid;
        grid-template-columns: 1fr auto;
        margin: 0;
      }
      .profile-card dt,
      .profile-card dd {
        margin: 0;
        padding: 6px;
        border-bottom: 1px solid var(--line);
      }
      .profile-card dd {
        color: var(--aqua);
        text-align: right;
      }
      .meter {
        height: 8px;
        margin: 6px;
        background: var(--well);
        border: 1px solid #111;
      }
      .meter i {
        display: block;
        height: 100%;
        background: var(--green);
      }
      .status-message {
        padding: 10px;
        color: var(--muted);
      }
      .status-message strong {
        display: block;
        margin-bottom: 5px;
        color: var(--fg);
      }
      .review-list li {
        display: grid;
        grid-template-columns: 55px 1fr auto;
        gap: 8px;
        padding: 7px;
        border-bottom: 1px solid var(--line);
      }
      .review-list .result {
        color: var(--aqua);
      }
      .status {
        justify-content: space-between;
        color: var(--muted);
      }
      .status strong {
        color: var(--green);
      }
      @media (max-width: 760px) {
        .grid {
          grid-template-columns: 1fr;
          grid-template-rows: minmax(330px, 1fr) 145px;
        }
        .bank,
        .profile {
          display: none;
        }
        .arena,
        .review {
          grid-column: 1;
        }
        .review-list li {
          grid-template-columns: 35px 1fr;
        }
        .review-list .result {
          display: none;
        }
      }
      @media (max-width: 440px) {
        .utility .context,
        .status .hint {
          display: none;
        }
        .question-area {
          padding: 10px;
        }
        .prompt {
          font-size: 24px;
        }
        .answer {
          font-size: 10px;
          padding: 3px;
        }
      }`;
