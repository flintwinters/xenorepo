/** Typed WIRE/98 account, publishing, pagination, and event-stream client. */
import { Component, render } from "preact";
import {
  authenticate, logout, posts as loadPosts, publish, session as loadSession, setLike,
  type Post, type Session,
} from "./client.js";
import "./styles.css";

type Mode = "login" | "register";
interface State {
  session: Session;
  mode: Mode;
  posts: Post[];
  body: string;
  authMessage: string;
  authFailed: boolean;
  offerRegistration: boolean;
  message: string;
  failed: boolean;
  lastSync: string;
  mobileAccount: boolean;
}

const GUEST: Session = { authenticated: false, account: null };

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed.";
}

class Microblog extends Component<Record<string, never>, State> {
  override state: State = {
    session: GUEST, mode: "login", posts: [], body: "",
    authMessage: "ENTER ACCOUNT CREDENTIALS", authFailed: false, offerRegistration: false,
    message: "READY", failed: false, lastSync: "NEVER", mobileAccount: false,
  };
  private events?: EventSource;
  private refreshTimer?: number;

  override componentDidMount(): void {
    void this.initialize();
    this.connectLiveFeed();
    this.refreshTimer = window.setInterval(() => void this.refresh(true), 120_000);
  }

  override componentWillUnmount(): void {
    this.events?.close();
    window.clearInterval(this.refreshTimer);
  }

  private notice(message: string, failed = false): void {
    this.setState({ message, failed });
  }

  private async initialize(): Promise<void> {
    try {
      const session = await loadSession();
      this.setState({ session });
      await this.refresh(true);
    } catch (error) {
      this.notice(errorText(error), true);
    }
  }

  private async refresh(silent = false): Promise<void> {
    try {
      const posts = await loadPosts();
      this.setState({ posts, lastSync: new Date().toLocaleTimeString() });
      if (!silent) this.notice("STREAM SYNCHRONIZED");
    } catch (error) {
      this.notice(errorText(error), true);
    }
  }

  private connectLiveFeed(): void {
    this.events = new EventSource("/api/events");
    this.events.addEventListener("feed", () => void this.refresh(true));
    this.events.onerror = () => this.notice("LIVE LINK RETRYING", true);
    this.events.onopen = () => {
      if (this.state.message === "LIVE LINK RETRYING") this.notice("LIVE LINK ACTIVE");
    };
  }

  private setMode = (mode: Mode): void => {
    this.setState({ mode, authFailed: false, offerRegistration: false,
      authMessage: mode === "login" ? "ENTER ACCOUNT CREDENTIALS" : "CHOOSE NEW ACCOUNT CREDENTIALS" });
  };

  private submitAuth = (event: SubmitEvent): void => {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const handle = (form.elements.namedItem("handle") as HTMLInputElement).value;
    const password = form.elements.namedItem("password") as HTMLInputElement;
    const signingIn = this.state.mode === "login";
    this.setState({ authMessage: signingIn ? "SIGNING IN…" : "REGISTERING…",
      authFailed: false, offerRegistration: false });
    void authenticate(this.state.mode, { handle, password: password.value }).then((session) => {
      password.value = "";
      this.setState({ session, authMessage: "ENTER ACCOUNT CREDENTIALS" });
      this.notice(signingIn ? "LINK ESTABLISHED" : "ACCOUNT CREATED");
    }).catch((error: unknown) => {
      password.value = "";
      this.setState({ authMessage: errorText(error), authFailed: true, offerRegistration: signingIn });
      password.focus();
      this.notice(signingIn ? "SIGN-IN FAILED" : "REGISTRATION FAILED", true);
    });
  };

  private signOut = (): void => {
    void logout().then((session) => {
      this.setState({ session, mobileAccount: false });
      this.notice("LINK CLOSED");
    }).catch((error: unknown) => this.notice(errorText(error), true));
  };

  private submitPost = (event: SubmitEvent): void => {
    event.preventDefault();
    void publish(this.state.body).then((post) => {
      this.setState((state) => ({ posts: [post, ...state.posts], body: "" }));
      this.notice("TRANSMISSION PUBLISHED");
    }).catch((error: unknown) => this.notice(errorText(error), true));
  };

  private composeKey = (event: KeyboardEvent): void => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing || event.repeat) return;
    event.preventDefault();
    (event.currentTarget as HTMLTextAreaElement).form?.requestSubmit();
  };

  private like = (post: Post): void => {
    void setLike(post).then((updated) => {
      this.setState((state) => ({ posts: state.posts.map((item) => item.id === updated.id ? updated : item) }));
      this.notice(updated.liked_by_me ? "SIGNAL ADDED" : "SIGNAL REMOVED");
    }).catch((error: unknown) => this.notice(errorText(error), true));
  };

  private accountPane(): preact.JSX.Element {
    const { mode, session } = this.state;
    return <aside class={`pane account${this.state.mobileAccount ? " mobile-open" : ""}`}
      aria-labelledby="account-title">
      <div class="title blue" id="account-title"><span class="plaque">01</span>ACCOUNT LINK</div>
      <div class="account-body">{session.authenticated && session.account
        ? <div id="signed" class="signed"><div>LINK ACTIVE</div>
          <p class="handle" id="signedHandle">@{session.account.handle}</p>
          <button id="logout" onClick={this.signOut}>SIGN OUT</button></div>
        : <div id="guest"><div class="tabs" role="tablist">
          <button class={`tab${mode === "login" ? " active" : ""}`} id="loginTab" type="button"
            onClick={() => this.setMode("login")}>SIGN IN</button>
          <button class={`tab${mode === "register" ? " active" : ""}`} id="registerTab" type="button"
            onClick={() => this.setMode("register")}>REGISTER</button></div>
          <form id="authForm" onSubmit={this.submitAuth}>
            <label class="field">HANDLE<input id="handle" name="handle" autocomplete="username"
              minlength={3} maxlength={20} pattern="[a-z0-9_]+" required /></label>
            <label class="field">PASSWORD<input id="password" name="password" type="password"
              autocomplete={mode === "login" ? "current-password" : "new-password"}
              minlength={8} maxlength={128} required /></label>
            <button id="authSubmit">{mode === "login" ? "SIGN IN" : "REGISTER"}</button>
          </form>
          <div class={`auth-message${this.state.authFailed ? " error" : ""}`} id="authMessage"
            role="alert" aria-live="assertive">{this.state.authMessage}
            {this.state.offerRegistration && <><br /><button type="button"
              onClick={() => this.setMode("register")}>REGISTER THIS HANDLE</button></>}</div></div>}</div>
    </aside>;
  }

  private feed(): preact.JSX.Element {
    if (!this.state.posts.length) return <div class="empty">NO TRANSMISSIONS RECORDED</div>;
    return <>{this.state.posts.map((post) => <article class="post" data-id={post.id} key={post.id}>
      <div class="post-head"><span class="post-author">@{post.author}</span><span>#{post.id}</span>
        <time class="post-time">{new Date(post.created_at).toLocaleString()}</time></div>
      <div class="post-body">{post.body}</div><div class="post-actions">
        <button class={`like${post.liked_by_me ? " liked" : ""}`} disabled={!this.state.session.authenticated}
          onClick={() => this.like(post)}>{post.liked_by_me ? "UNLIKE" : "LIKE"}</button>
        <span>{post.like_count} SIGNAL{post.like_count === 1 ? "" : "S"}</span>
      </div></article>)}</>;
  }

  override render(): preact.JSX.Element {
    const active = this.state.session.authenticated;
    return <div class="frame"><header class="rail">
      <span class="brand">WIRE/98</span><span class="summary">PUBLIC MICROBLOG CIRCUIT</span>
      <span id="identity">{active ? `@${this.state.session.account!.handle}` : "GUEST"}</span>
      <button class="mobile-account" id="accountCommand"
        onClick={() => this.setState((state) => ({ mobileAccount: !state.mobileAccount }))}>ACCOUNT</button>
      <button id="refresh" onClick={() => void this.refresh()}>REFRESH</button></header>
      <main class="workspace">{this.accountPane()}<section class="pane main" aria-labelledby="feed-title">
        <div><div class="title" id="feed-title"><span class="plaque">02</span>TRANSMISSION STREAM</div>
          <form class="composer" id="postForm" onSubmit={this.submitPost}>
            <label for="body">NEW TRANSMISSION</label><textarea id="body" maxlength={280}
              placeholder={active ? "What is on the wire?" : "Sign in to publish."} disabled={!active}
              value={this.state.body} onInput={(event) => this.setState({ body: event.currentTarget.value })}
              onKeyDown={this.composeKey} />
            <div class="compose-row"><button id="publish" disabled={!active}>PUBLISH</button>
              <span id="composeHint">{active ? "READY" : "AUTHENTICATION REQUIRED"}</span>
              <output class="counter" id="counter">{this.state.body.length}/280</output></div>
          </form></div><div class="feed" id="feed" aria-live="polite">{this.feed()}</div>
      </section></main><footer class="rail status"><span class="signal">● ONLINE</span>
        <span id="message" class={this.state.failed ? "error" : ""}>{this.state.message}</span>
        <span class="summary" /><span class="low">LAST SYNC:</span>
        <time id="lastSync">{this.state.lastSync}</time></footer></div>;
  }
}

export function mount(root: HTMLElement | null): void {
  if (!root) throw new Error("missing application mount");
  document.title = "WIRE/98";
  render(<Microblog />, root);
}
