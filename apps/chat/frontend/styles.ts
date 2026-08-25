import { css } from "lit";

export const chatStyles = css`
  :host { display:block; height:100%; color:#ebdbb2; font:12px/1.35 "Courier New",monospace; background:#1d2021; }
  * { box-sizing:border-box; } x-console-shell { height:100%; } .brand { color:#fabd2f; font-weight:bold; letter-spacing:.08em; }
  .context { color:#a89984; } .connection { margin-left:auto; }
  .mosaic { min-height:0; display:grid; grid-template-columns:176px minmax(360px,1fr) 220px; grid-template-rows:minmax(0,1fr) 145px; gap:1px; background:#111; }
  x-console-pane { min-width:0; min-height:0; } .roster { grid-row:1/3; } .stream { grid-column:2; } .details { grid-column:3; } .compose { grid-column:2/4; grid-row:2; }
  .channel-list { margin:0; padding:5px; list-style:none; } .channel { width:100%; margin-bottom:4px; text-align:left; } .channel strong { float:right; color:#b8bb26; }
  .notice { margin:8px; padding:7px; color:#a89984; background:#181a1b; border:1px inset #504945; }
  .messages { height:100%; overflow-y:auto; background:linear-gradient(#171918,#202320); scrollbar-color:#665c54 #181a1b; }
  .message { display:grid; grid-template-columns:62px 112px minmax(0,1fr); min-height:29px; border-bottom:1px solid #3c3836; }
  .message time,.message b,.message p { margin:0; padding:6px 8px; } .message time { color:#a89984; text-align:right; border-right:1px solid #504945; }
  .message b { color:#8ec07c; overflow:hidden; text-overflow:ellipsis; border-right:1px solid #504945; } .message p { white-space:pre-wrap; overflow-wrap:anywhere; }
  dl { display:grid; grid-template-columns:1fr auto; margin:0; } dt,dd { margin:0; padding:6px 7px; border-bottom:1px solid #504945; } dd { color:#8ec07c; text-align:right; }
  .compose-form { height:100%; display:grid; grid-template-columns:175px minmax(0,1fr) 82px; grid-template-rows:25px minmax(0,1fr); gap:5px; padding:7px; }
  .field-label { display:flex; align-items:center; color:#a89984; } input,textarea { width:100%; min-width:0; padding:5px 7px; color:#ebdbb2; font:inherit; background:#181a1b; border:1px solid #111; box-shadow:inset 1px 1px 3px #000; resize:none; }
  input:focus-visible,textarea:focus-visible { outline:2px solid #fabd2f; outline-offset:1px; } .name { grid-column:1; grid-row:2; } .message-input { grid-column:2; grid-row:1/3; } .send { grid-column:3; grid-row:1/3; font-weight:bold; color:#b8bb26; }
  .status { justify-content:space-between; } .status strong { color:#b8bb26; } kbd { padding:0 3px; color:#ebdbb2; background:#3c3836; border:1px solid #504945; }
  @media(max-width:850px) { .mosaic { grid-template-columns:165px minmax(330px,1fr); } .details { display:none; } .compose { grid-column:2; } .context { display:none; } }
  @media(max-width:570px) { .mosaic { grid-template-columns:1fr; grid-template-rows:minmax(0,1fr) 155px; } .roster,.hint { display:none; } .stream,.compose { grid-column:1; } .message { grid-template-columns:52px 86px minmax(0,1fr); } .compose-form { grid-template-columns:108px minmax(0,1fr) 60px; grid-template-rows:24px minmax(0,1fr); } }
`;
