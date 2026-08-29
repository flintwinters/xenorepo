/** Common Room's Preact mount boundary. */

import { render } from "preact";
import { ChatRoom } from "./room.js";

export function mount(root: HTMLElement): void {
  render(<ChatRoom />, root);
}
