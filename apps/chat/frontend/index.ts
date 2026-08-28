/** Common Room's registration and mount boundary. */

import { ChatRoom } from "./room.js";

if (!customElements.get("x-chat-room")) customElements.define("x-chat-room", ChatRoom);

export function mount(root: HTMLElement): void {
  root.replaceChildren(document.createElement("x-chat-room"));
}
