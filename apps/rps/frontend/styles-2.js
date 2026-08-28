export const styles2 = String.raw`
      .signal-ready {
        --signal: var(--orange);
      }
      .signal-win {
        --signal: var(--green);
      }
      .signal-loss,
      .signal-error {
        --signal: var(--red);
      }
      .signal-tie {
        --signal: var(--purple);
      }
      .frame .utility {
        border-bottom: 5px solid var(--signal);
      }
      .frame .battle {
        box-shadow: inset 0 0 0 7px var(--signal);
      }
      .frame .battle > .pane-title {
        background: var(--signal);
      }
      .frame .instrument {
        position: relative;
        box-shadow: inset 0 0 0 5px var(--signal);
      }
      .frame .clock,
      .frame .outcome {
        color: var(--signal);
      }
      .frame .throws {
        border-block: 5px solid var(--signal);
      }
      .battle-body {
        grid-template-rows: 42px 1fr auto 38px 42px;
      }
      .message {
        display: grid;
        place-items: center;
        background: var(--signal);
        color: #1d2021;
        font-size: 16px;
        font-weight: bold;
        letter-spacing: 0.04em;
        border: 0;
      }
      .player-strip.ready {
        box-shadow: inset 7px 0 var(--signal);
      }
      .result {
        position: absolute;
        z-index: 2;
        inset: 12px max(18px, 8%);
        grid-template-columns: 1fr minmax(82px, 0.55fr) 1fr;
        background: #1d2021;
        border: 7px solid var(--signal);
        box-shadow: 0 6px 0 #101112;
      }
      .result > div:first-child {
        align-self: stretch;
        display: grid;
        place-content: center;
        background: #203537;
        border-right: 3px solid var(--aqua);
      }
      .result > div:last-child {
        align-self: stretch;
        display: grid;
        place-content: center;
        background: #3c2d20;
        border-left: 3px solid var(--orange);
      }
      .pick {
        font-family: "Segoe UI Emoji", "Noto Color Emoji", sans-serif;
        font-size: clamp(48px, 8vw, 82px);
        line-height: 1;
      }
      .outcome {
        font-size: 22px;
        font-weight: bold;
      }
      .standby.searching {
        gap: 8px;
        color: var(--yellow);
        font-weight: bold;
      }
      .standby.searching::after {
        content: "";
        width: 28px;
        height: 5px;
        background: linear-gradient(
          90deg,
          var(--yellow) 25%,
          transparent 25% 40%,
          var(--yellow) 40% 65%,
          transparent 65% 80%,
          var(--yellow) 80%
        );
        background-size: 40px 100%;
        animation: queue-scan 0.7s linear infinite;
      }
      .throw.selected {
        position: relative;
        color: #1d2021;
        background: var(--aqua);
        border-color: #c7e8b9;
        box-shadow:
          inset 0 0 0 2px #203537,
          0 0 0 2px var(--aqua);
        animation: selection-lock 0.3s ease-out;
      }
      .throw.selected::after {
        content: "LOCKED";
        position: absolute;
        right: 5px;
        bottom: 2px;
        font-size: 8px;
        font-weight: bold;
      }
      .result.result-reveal {
        animation: reveal-in 0.32s cubic-bezier(0.2, 0.9, 0.25, 1.25) both;
      }
      .result.result-win {
        box-shadow:
          0 6px 0 #101112,
          0 0 28px rgb(184 187 38/0.55);
      }
      .result.result-loss {
        box-shadow:
          0 6px 0 #101112,
          0 0 28px rgb(251 73 52/0.5);
      }
      .result.result-tie {
        box-shadow:
          0 6px 0 #101112,
          0 0 28px rgb(211 134 155/0.5);
      }
      .result.result-finish {
        animation: result-hold 0.75s ease-in-out both;
      }
      .message {
        transition:
          background-color 0.18s ease,
          color 0.18s ease,
          transform 0.18s ease;
      }
      .message.message-announce {
        animation: message-arrive 0.22s ease-out;
      }
      .signal-search .battle {
        animation: queue-pulse 1.2s ease-in-out infinite;
      }
      .signal-win .battle {
        animation: win-flash 0.65s ease-out;
      }
      .signal-loss .battle {
        animation: loss-shake 0.45s ease-out;
      }
      .signal-tie .battle {
        animation: tie-wave 0.55s ease-out;
      }
      @keyframes queue-scan {
        to {
          background-position: 40px 0;
        }
      }
      @keyframes selection-lock {
        0% {
          transform: scale(0.94);
        }
        55% {
          transform: scale(1.04);
        }
        100% {
          transform: scale(1);
        }
      }
      @keyframes reveal-in {
        0% {
          opacity: 0;
          transform: scale(0.68) rotateX(18deg);
        }
        100% {
          opacity: 1;
          transform: scale(1) rotateX(0);
        }
      }
      @keyframes result-hold {
        0%,
        100% {
          transform: scale(1);
        }
        50% {
          transform: scale(1.025);
        }
      }
      @keyframes message-arrive {
        from {
          transform: translateY(7px);
          filter: brightness(1.5);
        }
        to {
          transform: translateY(0);
          filter: brightness(1);
        }
      }
      @keyframes queue-pulse {
        50% {
          box-shadow:
            inset 0 0 0 7px var(--signal),
            inset 0 0 24px rgb(250 189 47/0.18);
        }
      }
      @keyframes win-flash {
        0% {
          filter: brightness(1);
        }
        35% {
          filter: brightness(1.55);
        }
        100% {
          filter: brightness(1);
        }
      }
      @keyframes loss-shake {
        20%,
        60% {
          transform: translateX(-5px);
        }
        40%,
        80% {
          transform: translateX(5px);
        }
      }
      @keyframes tie-wave {
        50% {
          filter: hue-rotate(16deg) brightness(1.18);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        *,
        *::before,
        *::after {
          animation-duration: 0.01ms !important;
          animation-iteration-count: 1 !important;
          scroll-behavior: auto !important;
          transition-duration: 0.01ms !important;
        }
      }
      .result {
        grid-template-columns: 1fr;
        grid-template-rows: 1fr auto 1fr;
      }
      .result > div:first-child {
        grid-row: 1;
        background: #3c2d20;
        border: 0;
        border-bottom: 3px solid var(--orange);
      }
      .result > .outcome {
        grid-row: 2;
      }
      .result > div:last-child {
        grid-row: 3;
        background: #203537;
        border: 0;
        border-top: 3px solid var(--aqua);
      }
      .result.result-reveal > div:first-child .pick {
        animation: their-swoop 0.72s cubic-bezier(0.2, 0.8, 0.25, 1) both;
      }
      .result.result-reveal > div:last-child .pick {
        animation: your-swoop 0.72s cubic-bezier(0.2, 0.8, 0.25, 1) both;
      }
      @keyframes their-swoop {
        0% {
          transform: translate(72%, 55%) scale(0.72) rotate(22deg);
        }
        58% {
          transform: translate(0, 112%) scale(1.28) rotate(-8deg);
        }
        76% {
          transform: translate(-8%, 96%) scale(1.08);
        }
        100% {
          transform: translate(0) scale(1) rotate(0);
        }
      }
      @keyframes your-swoop {
        0% {
          transform: translate(-72%, -55%) scale(0.72) rotate(-22deg);
        }
        58% {
          transform: translate(0, -112%) scale(1.28) rotate(8deg);
        }
        76% {
          transform: translate(8%, -96%) scale(1.08);
        }
        100% {
          transform: translate(0) scale(1) rotate(0);
        }
      }
      @media (max-width: 850px) {
        .mosaic {
          grid-template-columns: 170px 1fr;
        }
      }
      @media (max-width: 590px) {
        html,
        body {
          min-height: 100%;
          overflow: auto;
          background: #111;
        }
        body {
          padding-bottom: env(safe-area-inset-bottom);
        }
        .landing,
        .frame {
          height: auto;
          min-height: 100dvh;
        }
        .landing {
          grid-template-rows: 32px auto 28px;
        }
        .landing-utility {
          padding-inline: max(8px, env(safe-area-inset-left)) max(8px, env(safe-area-inset-right));
        }
        .landing-mosaic {
          grid-template-columns: 1fr;
          grid-template-rows: minmax(260px, 1fr) minmax(180px, auto);
        }
        .entry-body {
          padding: 24px 16px;
        }
        .landing-stats {
          gap: 6px;
          font-size: 11px;
        }
        .play-form {
          grid-template-columns: 1fr;
        }
        .play {
          width: 100%;
          min-height: 48px;
        }
        .mosaic {
          grid-template-columns: 1fr;
          grid-template-rows: minmax(500px, 1fr) minmax(148px, auto) minmax(180px, auto);
          overflow: visible;
        }
        .arena-index,
        .battle,
        .ledger {
          grid-column: 1;
        }
        .battle {
          grid-row: 1;
          min-height: 500px;
        }
        .ledger {
          grid-row: 2;
        }
        .arena-index {
          grid-row: 3;
          min-height: 180px;
        }
        .arena-index .pane-body {
          max-height: 260px;
        }
        .utility {
          min-height: 44px;
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 4px 8px;
          padding: 5px max(8px, env(safe-area-inset-right)) 5px max(8px, env(safe-area-inset-left));
        }
        .utility .key {
          margin-left: 0;
          min-height: 34px;
        }
        .utility .link {
          grid-column: 1/-1;
          justify-self: end;
          font-size: 10px;
        }
        .battle-body {
          grid-template-rows: 46px 1fr auto 42px 46px;
        }
        .player-strip {
          padding: 7px 10px;
        }
        .instrument {
          grid-template-columns: 64px 1fr;
        }
        .clock {
          font-size: 28px;
        }
        .result {
          inset: 10px 8px;
          border-width: 5px;
          grid-template-columns: 1fr;
        }
        .pick {
          font-size: clamp(46px, 17vw, 68px);
        }
        .outcome {
          font-size: 16px;
        }
        .throws {
          gap: 4px;
          padding: 6px;
        }
        .throw {
          min-height: 48px;
          grid-template-columns: 16px 1fr;
          text-align: center;
          font-size: 11px;
        }
        .throw span:first-child {
          font-size: 15px;
        }
        .throw .shortcut {
          display: none;
        }
        .message {
          font-size: 13px;
          line-height: 1.15;
          padding: 4px 8px;
          text-align: center;
        }
        .shortcut {
          display: none;
        }
        .metrics dt,
        .metrics dd {
          padding: 7px;
        }
        .pane-title {
          min-height: 26px;
        }
        .ledger .pane-body {
          max-height: 190px;
        }
      }
      @media (max-width: 360px) {
        .brand {
          font-size: 11px;
        }
        .landing-stats {
          font-size: 10px;
        }
        .result {
          grid-template-columns: 1fr;
        }
        .pick {
          font-size: 42px;
        }
        .outcome {
          font-size: 14px;
        }
        .name {
          font-size: 12px;
        }
        .streak {
          font-size: 10px;
        }
      }`;
