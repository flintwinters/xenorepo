import { LitElement, html, nothing } from "lit";
import "@xenorepo/lit-ui";
import { ChatTransport } from "./socket.js";
import { chatStyles } from "./styles.js";
import type { ChatMessage, ConnectionState, ServerEvent } from "./types.js";

const PARTICIPANT_KEY = "common98-participant";
const NAME_KEY = "common98-name";

export class ChatRoom extends LitElement {
  static properties = {
    messages: { state: true },
    connection: { state: true },
    online: { state: true },
    clock: { state: true },
    author: { state: true },
    body: { state: true },
    error: { state: true },
  };
  static styles = chatStyles;

  declare messages: ChatMessage[];
  declare connection: ConnectionState;
  declare online: number | undefined;
  declare clock: string;
  declare author: string;
  declare body: string;
  declare error: string;
  private synced = false;
  private pending: ChatMessage[] = [];
  private seen = new Set<number>();
  private clockTimer?: number;
  private readonly participantId = localStorage.getItem(PARTICIPANT_KEY) || crypto.randomUUID();
  private readonly transport = new ChatTransport({
    opened: () => {
      this.connection = "online";
      this.identify();
    },
    event: (event) => this.receive(event),
    closed: () => {
      this.connection = "offline";
      this.synced = false;
      this.pending = [];
    },
  });

  constructor() {
    super();
    this.messages = [];
    this.connection = "connecting";
    this.online = undefined;
    this.clock = "--:--:--";
    this.author = "";
    this.body = "";
    this.error = "";
  }

  connectedCallback(): void {
    super.connectedCallback();
    localStorage.setItem(PARTICIPANT_KEY, this.participantId);
    this.author = localStorage.getItem(NAME_KEY) || `Guest-${Math.random().toString(16).slice(2, 6).toUpperCase()}`;
    this.clockTimer = window.setInterval(
      () => (this.clock = new Date().toLocaleTimeString([], { hour12: false })),
      1000,
    );
    this.transport.connect();
  }

  disconnectedCallback(): void {
    window.clearInterval(this.clockTimer);
    this.transport.disconnect();
    super.disconnectedCallback();
  }

  private identify(): void {
    this.transport.send({ type: "hello", participant_id: this.participantId, author: this.author.trim() });
  }

  private add(message: ChatMessage): void {
    if (this.seen.has(message.id)) return;
    this.seen.add(message.id);
    this.messages = [...this.messages, message];
    void this.updateComplete.then(() => {
      const log = this.renderRoot.querySelector<HTMLElement>(".messages");
      if (log) log.scrollTop = log.scrollHeight;
    });
  }

  private receive(event: ServerEvent): void {
    if (event.type === "history") {
      event.messages.forEach((message) => this.add(message));
      this.synced = true;
      this.pending.forEach((message) => this.add(message));
      this.pending = [];
      return;
    }
    if (event.type === "message") {
      this.synced ? this.add(event.message) : this.pending.push(event.message);
      return;
    }
    if (event.type === "presence") {
      this.online = event.count;
      return;
    }
    this.error = event.message;
  }

  private submit(event: SubmitEvent): void {
    event.preventDefault();
    const author = this.author.trim(),
      body = this.body.trim();
    if (!author || !body) return;
    localStorage.setItem(NAME_KEY, author);
    this.identify();
    if (this.transport.send({ type: "message", author, body, client_message_id: crypto.randomUUID() })) {
      this.body = "";
      this.error = "";
      void this.updateComplete.then(() => this.renderRoot.querySelector<HTMLTextAreaElement>("textarea")?.focus());
    }
  }

  private messageKey(event: KeyboardEvent): void {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      (event.currentTarget as HTMLTextAreaElement).form?.requestSubmit();
    }
  }

  render() {
    const live = this.connection === "online";
    return html`<x-console-shell aria-label="Common Room live chat">
      <x-utility-rail slot="header"
        ><span class="brand">▣ COMMON/98</span><span class="context">PUBLIC CHANNEL / NO ACCOUNT REQUIRED</span
        ><x-status-indicator
          class="connection"
          .label=${live ? "LIVE" : this.connection === "offline" ? "RETRYING" : "CONNECTING"}
          tone=${live ? "green" : this.connection === "offline" ? "orange" : "blue"}
        ></x-status-indicator
      ></x-utility-rail>
      <section class="mosaic">
        <x-console-pane class="roster" title="CHANNEL INDEX"
          ><ul class="channel-list">
            <li>
              <x-command-button class="channel" pressed># COMMON <strong>LIVE</strong></x-command-button>
            </li>
          </ul>
          <div class="notice">
            One public room. Every visitor can read the complete record and speak immediately.
          </div></x-console-pane
        >
        <x-console-pane
          class="stream"
          title=${`MESSAGE STREAM · ${this.messages.length} ${this.messages.length === 1 ? "ENTRY" : "ENTRIES"}`}
          tone="green"
          ><div class="messages" role="log" aria-live="polite" aria-relevant="additions">
            ${this.messages.length
              ? this.messages.map(
                  (message) =>
                    html`<article class="message">
                      <time datetime=${message.created_at}
                        >${new Date(message.created_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                          hour12: false,
                        })}</time
                      ><b>${message.author}</b>
                      <p>${message.body}</p>
                    </article>`,
                )
              : html`<x-empty-state heading="NO MESSAGES YET" detail="OPEN THE CHANNEL BELOW"></x-empty-state>`}
          </div></x-console-pane
        >
        <x-console-pane class="details" title="CHANNEL STATE" tone="orange"
          ><dl>
            <dt>ACCESS</dt>
            <dd>OPEN</dd>
            <dt>HISTORY</dt>
            <dd>COMPLETE</dd>
            <dt>ONLINE</dt>
            <dd>${this.online ?? "—"}</dd>
            <dt>TRANSPORT</dt>
            <dd>${live ? "LIVE" : this.connection.toUpperCase()}</dd>
          </dl>
          <div class="notice">Messages are shared live and retained on this server.</div></x-console-pane
        >
        <x-console-pane class="compose" title="TRANSMIT" tone="purple"
          ><form class="compose-form" @submit=${this.submit}>
            <label class="field-label" for="name">DISPLAY NAME</label
            ><input
              class="name"
              id="name"
              maxlength="40"
              aria-label="Display name"
              .value=${this.author}
              @input=${(event: InputEvent) => (this.author = (event.target as HTMLInputElement).value)}
              @change=${() => localStorage.setItem(NAME_KEY, this.author.trim())}
            /><textarea
              class="message-input"
              maxlength="2000"
              placeholder="Write to everyone…"
              aria-label="Message"
              required
              .value=${this.body}
              @input=${(event: InputEvent) => (this.body = (event.target as HTMLTextAreaElement).value)}
              @keydown=${this.messageKey}
            ></textarea
            ><x-command-button
              class="send"
              .disabled=${!live}
              @click=${(event: Event) => (event.currentTarget as Element).closest("form")?.requestSubmit()}
              >SEND<br /><small>ENTER</small></x-command-button
            >
          </form></x-console-pane
        >
      </section>
      <x-status-rail slot="footer" class="status"
        ><strong>${live ? "● NOMINAL" : "● LINK DOWN"}</strong
        ><span class="hint"><kbd>ENTER</kbd> SEND · <kbd>SHIFT+ENTER</kbd> NEW LINE</span
        ><span role="alert">${this.error || nothing}</span><span>${this.clock}</span></x-status-rail
      >
    </x-console-shell>`;
  }
}
