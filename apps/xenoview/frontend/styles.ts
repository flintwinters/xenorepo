/** Dense operational presentation for repository evidence. */
import { css } from "lit";
import { consoleControls } from "@xenorepo/lit-ui";

export const cockpitStyles = [consoleControls, css`
  :host { display: block; height: 100%; color: #ebdbb2; font: 12px/1.45 "Courier New", monospace; }
  * { box-sizing: border-box; }
  x-console-shell { height: 100%; }
  main { min-height: 0; }
  .brand { color: #fabd2f; font-weight: 800; letter-spacing: .12em; }
  nav { display: flex; gap: 3px; margin-left: 12px; }
  .push { margin-left: auto; }
  .ok { color: #b8bb26; font-weight: bold; }
  .error { color: #fb4934; font-weight: bold; }
  .page { min-height: 100%; padding: 22px; background: #1d2021;
    background-image: linear-gradient(#ffffff05 1px, transparent 1px),
      linear-gradient(90deg, #ffffff04 1px, transparent 1px);
    background-size: 32px 32px; }
  .page-heading { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 18px;
    padding-bottom: 12px; border-bottom: 1px solid #504945; }
  h1 { margin: 2px 0 0; color: #fbf1c7; font-size: clamp(20px, 3vw, 34px); line-height: 1; letter-spacing: -.04em; }
  h2 { margin: 0; font-size: 12px; }
  .eyebrow { margin: 0; color: #83a598; font-weight: bold; letter-spacing: .14em; text-transform: uppercase; }
  .page-heading > p { margin: 0; color: #a89984; }
  .metrics { display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 7px; }
  .metric { min-height: 100px; display: flex; flex-direction: column; padding: 11px; border: 1px solid #665c54;
    border-top: 3px solid #83a598; background: linear-gradient(145deg, #282828, #202223);
    box-shadow: 0 5px 14px #0005; }
  .metric span { color: #bdae93; text-transform: uppercase; letter-spacing: .05em; }
  .metric strong { margin: auto 0 2px; color: #fbf1c7; font-size: 25px; line-height: 1; }
  .metric small { color: #928374; }
  .metric .up { color: #fabd2f; } .metric .down { color: #b8bb26; }
  .split { display: grid; grid-template-columns: 3fr 2fr; gap: 8px; margin-top: 8px; }
  .evidence-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
  x-console-pane { border: 1px solid #3c3836; background: #282828; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 6px 9px; text-align: left; border-bottom: 1px solid #3c3836; }
  th { color: #83a598; font-size: 10px; letter-spacing: .06em; text-transform: uppercase; }
  td:not(:first-child), th:not(:first-child) { text-align: right; white-space: nowrap; }
  tr.total td { color: #fbf1c7; font-weight: bold; border-top: 2px solid #665c54; }
  .note { padding: 10px 14px; color: #bdae93; } .note b { color: #fabd2f; }
  .module-table { overflow: auto; border: 1px solid #504945; background: #202223; }
  .module-table strong { color: #d3869b; }
  .module-table td:nth-child(2), .module-table td:last-child { text-align: left; }
  .module-table td:first-child small {
    display: block; margin-top: 2px; color: #928374; white-space: normal; }
  .module-table td:nth-child(2), .module-table td:nth-child(3) {
    min-width: 260px; color: #bdae93; text-align: left; white-space: normal; }
  .tree { overflow: auto; border: 1px solid #504945; background: #202223ee; }
  details details { border-left: 1px solid #3c3836; }
  .tree-row { min-height: 19px; display: grid;
    grid-template-columns: minmax(260px, 1fr) 110px 90px; align-items: center;
    gap: 10px; padding: 0 9px 0 calc(9px + var(--depth) * 14px);
    border-bottom: 1px solid #343637; cursor: pointer; }
  .tree-row:hover { background: #3c3836; } .tree-row small { color: #928374; text-align: right; }
  .tree-row span { color: var(--ls-color, #bdae93); } summary::marker { color: #fabd2f; }
  .diagram { display: grid; grid-template-columns: .8fr 1fr .9fr 2fr 1fr; gap: 10px; margin-bottom: 10px; }
  .layer { min-width: 0; padding: 9px; border: 1px solid #3c3836; background: #202223bb; }
  .layer h2 { margin-bottom: 8px; color: #928374; text-transform: uppercase; letter-spacing: .08em; }
  .layer > div { display: grid; gap: 6px; }
  .node { min-width: 0; padding: 9px; border: 1px solid #665c54; background: #282828; box-shadow: 0 3px 8px #0005; }
  .node strong, .node small { display: block; overflow: hidden; text-overflow: ellipsis; }
  .node small { color: #928374; } .node.repository { border-top: 3px solid #fabd2f; }
  .node.platform { border-top: 3px solid #d3869b; } .node.runtime { border-top: 3px solid #83a598; }
  .node.app { border-left: 3px solid #b8bb26; } .node.storage { border-top: 3px solid #fe8019; }
  .edges { max-height: 250px; display: grid; grid-template-columns: repeat(2, 1fr); overflow: auto; }
  .edges div { display: grid; grid-template-columns: 1fr auto 1fr; gap: 7px;
    padding: 5px 9px; border-bottom: 1px solid #3c3836; }
  .edges span { color: #928374; } .edges b:last-child { text-align: right; }
  .history { overflow: auto; border: 1px solid #504945; background: #202223; }
  .history td { font-variant-numeric: tabular-nums; }
  .empty { padding: 40px; border: 1px dashed #665c54; color: #a89984; text-align: center; background: #202223; }
  .empty h2 { color: #fbf1c7; font-size: 18px; }
  @media (max-width: 1000px) { .metrics { grid-template-columns: repeat(3, 1fr); }
    .diagram { grid-template-columns: 1fr 1fr; }
    .split, .evidence-grid { grid-template-columns: 1fr; } }
  @media (max-width: 650px) { nav { overflow-x: auto; } .page { padding: 12px; }
    .metrics { grid-template-columns: repeat(2, 1fr); }
    .diagram { grid-template-columns: 1fr; } .edges { grid-template-columns: 1fr; }
    .page-heading { align-items: start; flex-direction: column; }
    .tree-row { grid-template-columns: minmax(170px, 1fr) 80px; } .tree-row small:last-child { display: none; } }
`];
