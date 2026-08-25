/** Worminal's composition boundary: register the desktop and mount one instance. */

import { WorminalDesktop, installFavicon } from "./desktop.js";

if (!customElements.get("worminal-desktop")) {
  customElements.define("worminal-desktop", WorminalDesktop);
}

export function mount(root: HTMLElement): void {
  installFavicon();
  root.replaceChildren(document.createElement("worminal-desktop"));
}
