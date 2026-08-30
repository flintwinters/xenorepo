import { Component, createRef } from "preact";
import {
  CommandButton, ConsolePane, ConsoleShell, ConsoleWorkspace, EmptyState, StatusRail, UtilityRail,
} from "@xenorepo/ui";
import { ChatTransport } from "./socket.js";
import type { ChatMessage, ConnectionState, ServerEvent } from "./types.js";
import "./styles.css";

const PARTICIPANT_KEY = "common98-participant";
const NAME_KEY = "common98-name";
interface ChatState {
  messages: ChatMessage[];
  connection: ConnectionState;
  online?: number;
  clock: string;
  author: string;
  body: string;
  error: string;
}

function StatusIndicator({ label, tone }: { label: string; tone: "blue" | "green" | "orange" }) {
  return (
    <span class={`connection indicator indicator-${tone}`}>
      <i />
      <span role="status">{label}</span>
    </span>
  );
}

export class ChatRoom extends Component<Record<string, never>, ChatState> {
  override state: ChatState = {
    messages: [],
    connection: "connecting",
    clock: "--:--:--",
    author: "",
    body: "",
    error: "",
  };
  private synced = false;
  private pending: ChatMessage[] = [];
  private readonly seen = new Set<number>();
  private clockTimer?: number;
  private focusComposer = false;
  private readonly messagesRef = createRef<HTMLDivElement>();
  private readonly composerRef = createRef<HTMLTextAreaElement>();
  private readonly participantId = localStorage.getItem(PARTICIPANT_KEY) || crypto.randomUUID();
  private readonly transport = new ChatTransport({
    opened: () => {
      this.setState({ connection: "online" });
      this.identify();
    },
    event: (event) => this.receive(event),
    closed: () => {
      this.synced = false;
      this.pending = [];
      this.setState({ connection: "offline" });
    },
  });

  override componentDidMount(): void {
    localStorage.setItem(PARTICIPANT_KEY, this.participantId);
    this.setState({
      author: localStorage.getItem(NAME_KEY) || `Guest-${Math.random().toString(16).slice(2, 6).toUpperCase()}`,
    });
    this.clockTimer = window.setInterval(
      () =>
        this.setState({
          clock: new Date().toLocaleTimeString([], { hour12: false }),
        }),
      1000,
    );
    this.transport.connect();
  }

  override componentDidUpdate(): void {
    const log = this.messagesRef.current;
    if (log) log.scrollTop = log.scrollHeight;
    if (this.focusComposer) {
      this.focusComposer = false;
      this.composerRef.current?.focus();
    }
  }

  override componentWillUnmount(): void {
    window.clearInterval(this.clockTimer);
    this.transport.disconnect();
  }

  private identify(): void {
    this.transport.send({ type: "hello", participant_id: this.participantId, author: this.state.author.trim() });
  }

  private add(message: ChatMessage): void {
    if (this.seen.has(message.id)) return;
    this.seen.add(message.id);
    this.setState((state) => ({ messages: [...state.messages, message] }));
  }

  private receive(event: ServerEvent): void {
    if (event.type === "history") {
      event.messages.forEach((item) => this.add(item));
      this.synced = true;
      this.pending.forEach((item) => this.add(item));
      this.pending = [];
    } else if (event.type === "message") {
      if (this.synced) this.add(event.message);
      else this.pending.push(event.message);
    } else if (event.type === "presence") this.setState({ online: event.count });
    else this.setState({ error: event.message });
  }

  private submit = (event: SubmitEvent): void => {
    event.preventDefault();
    const author = this.state.author.trim(),
      body = this.state.body.trim();
    if (!author || !body) return;
    localStorage.setItem(NAME_KEY, author);
    this.identify();
    if (this.transport.send({ type: "message", author, body, client_message_id: crypto.randomUUID() })) {
      this.focusComposer = true;
      this.setState({ body: "", error: "" });
    }
  };

  private messageKey = (event: KeyboardEvent): void => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      (event.currentTarget as HTMLTextAreaElement).form?.requestSubmit();
    }
  };

  private renderMessages() {
    if (!this.state.messages.length) return <EmptyState heading="NO MESSAGES YET" detail="OPEN THE CHANNEL BELOW" />;
    return this.state.messages.map((item) => (
      <article class="message" key={item.id}>
        <time dateTime={item.created_at}>
          {new Date(item.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
          })}
        </time>
        <b>{item.author}</b>
        <p>{item.body}</p>
      </article>
    ));
  }

  override render() {
    const live = this.state.connection === "online";
    const entryLabel = this.state.messages.length === 1 ? "ENTRY" : "ENTRIES";
    const label = live ? "LIVE" : this.state.connection === "offline" ? "RETRYING" : "CONNECTING";
    const tone = live ? "green" : this.state.connection === "offline" ? "orange" : "blue";
    const header = (
      <UtilityRail>
        <span class="brand">▣ COMMON/98</span>
        <span class="context">PUBLIC CHANNEL / NO ACCOUNT REQUIRED</span>
        <StatusIndicator label={label} tone={tone} />
      </UtilityRail>
    );
    const footer = (
      <StatusRail class="status">
        <strong>{live ? "● NOMINAL" : "● LINK DOWN"}</strong>
        <span class="hint">
          <kbd>ENTER</kbd> SEND · <kbd>SHIFT+ENTER</kbd> NEW LINE
        </span>
        <span role="alert">{this.state.error}</span>
        <span>{this.state.clock}</span>
      </StatusRail>
    );
    return (
      <ConsoleShell class="chat-shell" aria-label="Common Room live chat" header={header} footer={footer}>
        <ConsoleWorkspace class="mosaic">
          <ConsolePane class="roster" title="CHANNEL INDEX">
            <ul class="channel-list">
              <li>
                <CommandButton class="channel" pressed>
                  # COMMON <strong>LIVE</strong>
                </CommandButton>
              </li>
            </ul>
            <div class="notice">One public room. Every visitor can read the complete record and speak immediately.</div>
          </ConsolePane>
          <ConsolePane
            class="stream"
            title={`MESSAGE STREAM · ${this.state.messages.length} ${entryLabel}`}
            tone="green"
          >
            <div ref={this.messagesRef} class="messages" role="log" aria-live="polite" aria-relevant="additions">
              {this.renderMessages()}
            </div>
          </ConsolePane>
          <ConsolePane class="details" title="CHANNEL STATE" tone="orange">
            <dl>
              <dt>ACCESS</dt>
              <dd>OPEN</dd>
              <dt>HISTORY</dt>
              <dd>COMPLETE</dd>
              <dt>ONLINE</dt>
              <dd>{this.state.online ?? "—"}</dd>
              <dt>TRANSPORT</dt>
              <dd>{live ? "LIVE" : this.state.connection.toUpperCase()}</dd>
            </dl>
            <div class="notice">Messages are shared live and retained on this server.</div>
          </ConsolePane>
          <ConsolePane class="compose" title="TRANSMIT" tone="purple">
            <form class="compose-form" onSubmit={this.submit}>
              <label class="field-label" for="name">
                DISPLAY NAME
              </label>
              <input
                class="name"
                id="name"
                maxLength={40}
                aria-label="Display name"
                value={this.state.author}
                onInput={(event) => this.setState({ author: event.currentTarget.value })}
                onChange={() => localStorage.setItem(NAME_KEY, this.state.author.trim())}
              />
              <textarea
                ref={this.composerRef}
                class="message-input"
                maxLength={2000}
                placeholder="Write to everyone…"
                aria-label="Message"
                required
                value={this.state.body}
                onInput={(event) => this.setState({ body: event.currentTarget.value })}
                onKeyDown={this.messageKey}
              />
              <CommandButton
                class="send"
                disabled={!live}
                onClick={(event) => event.currentTarget.closest("form")?.requestSubmit()}
              >
                SEND
                <br />
                <small>ENTER</small>
              </CommandButton>
            </form>
          </ConsolePane>
        </ConsoleWorkspace>
      </ConsoleShell>
    );
  }
}
