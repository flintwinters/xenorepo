import { render } from "lit";
import { styles1 } from "./styles.js";
import { view } from "./view.js";

function start() {
  const $ = (id) => document.getElementById(id);
  let session = { authenticated: false, account: null },
    mode = "login",
    posts = [];
  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    let data;
    try {
      data = await response.json();
    } catch {
      data = { error: "Invalid server response." };
    }
    if (!response.ok) throw new Error(data.error || "Request failed.");
    return data;
  }
  function notice(text, bad = false) {
    $("message").textContent = text;
    $("message").style.color = bad ? "var(--red)" : "var(--yellow)";
  }
  function renderSession() {
    const active = session.authenticated;
    $("guest").classList.toggle("hidden", active);
    $("signed").classList.toggle("hidden", !active);
    $("identity").textContent = active ? "@" + session.account.handle : "GUEST";
    $("signedHandle").textContent = active ? "@" + session.account.handle : "";
    $("body").disabled = !active;
    $("publish").disabled = !active;
    $("body").placeholder = active ? "What is on the wire?" : "Sign in to publish.";
    $("composeHint").textContent = active ? "READY" : "AUTHENTICATION REQUIRED";
  }
  function escapeText(value) {
    const node = document.createElement("span");
    node.textContent = value;
    return node.innerHTML;
  }
  function renderPosts() {
    if (!posts.length) {
      $("feed").innerHTML = '<div class="empty">NO TRANSMISSIONS RECORDED</div>';
      return;
    }
    $("feed").innerHTML = posts
      .map(
        (post) => `<article class="post" data-id="${post.id}">
          <div class="post-head"><span class="post-author">@${escapeText(post.author)}</span>
          <span>#${post.id}</span><time class="post-time">
          ${new Date(post.created_at).toLocaleString()}</time></div>
          <div class="post-body">${escapeText(post.body)}</div><div class="post-actions">
          <button class="like ${post.liked_by_me ? "liked" : ""}"
          ${session.authenticated ? "" : "disabled"}>${post.liked_by_me ? "UNLIKE" : "LIKE"}</button>
          <span>${post.like_count} SIGNAL${post.like_count === 1 ? "" : "S"}</span></div></article>`,
      )
      .join("");
  }
  async function refresh(silent = false) {
    try {
      posts = await api("/api/posts?limit=100");
      renderPosts();
      $("lastSync").textContent = new Date().toLocaleTimeString();
      if (!silent) notice("STREAM SYNCHRONIZED");
    } catch (error) {
      notice(error.message, true);
    }
  }
  async function loadSession() {
    try {
      session = await api("/api/session");
      renderSession();
      await refresh(true);
    } catch (error) {
      notice(error.message, true);
    }
  }
  function setAuthMessage(text, bad = false, offerRegistration = false) {
    $("authMessage").classList.toggle("error", bad);
    $("authMessage").replaceChildren(document.createTextNode(text));
    if (offerRegistration) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "REGISTER THIS HANDLE";
      button.onclick = () => setMode("register");
      $("authMessage").append(document.createElement("br"), button);
    }
  }
  function setMode(next) {
    mode = next;
    $("loginTab").classList.toggle("active", mode === "login");
    $("registerTab").classList.toggle("active", mode === "register");
    $("authSubmit").textContent = mode === "login" ? "SIGN IN" : "REGISTER";
    $("password").autocomplete = mode === "login" ? "current-password" : "new-password";
    setAuthMessage(mode === "login" ? "ENTER ACCOUNT CREDENTIALS" : "CHOOSE NEW ACCOUNT CREDENTIALS");
  }
  $("loginTab").onclick = () => setMode("login");
  $("registerTab").onclick = () => setMode("register");
  $("refresh").onclick = () => refresh();
  $("accountCommand").onclick = () => document.querySelector(".account").classList.toggle("mobile-open");
  $("authForm").onsubmit = async (event) => {
    event.preventDefault();
    const signingIn = mode === "login";
    setAuthMessage(signingIn ? "SIGNING IN…" : "REGISTERING…");
    try {
      session = await api(signingIn ? "/api/sessions" : "/api/accounts", {
        method: "POST",
        body: JSON.stringify({ handle: $("handle").value, password: $("password").value }),
      });
      $("password").value = "";
      renderSession();
      renderPosts();
      notice(signingIn ? "LINK ESTABLISHED" : "ACCOUNT CREATED");
    } catch (error) {
      $("password").value = "";
      setAuthMessage(error.message, true, signingIn);
      $("password").focus();
      notice(signingIn ? "SIGN-IN FAILED" : "REGISTRATION FAILED", true);
    }
  };
  $("logout").onclick = async () => {
    try {
      session = await api("/api/session", { method: "DELETE" });
      document.querySelector(".account").classList.remove("mobile-open");
      renderSession();
      renderPosts();
      notice("LINK CLOSED");
    } catch (error) {
      notice(error.message, true);
    }
  };
  $("body").oninput = () => ($("counter").textContent = $("body").value.length + "/280");
  $("body").onkeydown = (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing && !event.repeat) {
      event.preventDefault();
      $("postForm").requestSubmit();
    }
  };
  $("postForm").onsubmit = async (event) => {
    event.preventDefault();
    try {
      const post = await api("/api/posts", { method: "POST", body: JSON.stringify({ body: $("body").value }) });
      posts.unshift(post);
      $("body").value = "";
      $("counter").textContent = "0/280";
      renderPosts();
      notice("TRANSMISSION PUBLISHED");
    } catch (error) {
      notice(error.message, true);
    }
  };
  $("feed").onclick = async (event) => {
    const button = event.target.closest(".like");
    if (!button) return;
    const article = button.closest(".post"),
      post = posts.find((item) => item.id === Number(article.dataset.id));
    try {
      const updated = await api(`/api/posts/${post.id}/like`, { method: post.liked_by_me ? "DELETE" : "PUT" });
      posts = posts.map((item) => (item.id === updated.id ? updated : item));
      renderPosts();
      notice(updated.liked_by_me ? "SIGNAL ADDED" : "SIGNAL REMOVED");
    } catch (error) {
      notice(error.message, true);
    }
  };
  function connectLiveFeed() {
    const events = new EventSource("/api/events");
    events.addEventListener("feed", () => refresh(true));
    events.onerror = () => notice("LIVE LINK RETRYING", true);
    events.onopen = () => {
      if ($("message").textContent === "LIVE LINK RETRYING") notice("LIVE LINK ACTIVE");
    };
  }
  loadSession();
  connectLiveFeed();
  setInterval(() => refresh(true), 120000);
}

export function mount(root) {
  if (!root) throw new Error("missing application mount");
  document.title = "WIRE/98";
  for (const content of [styles1]) {
    const style = document.createElement("style");
    style.textContent = content;
    document.head.append(style);
  }
  render(view, root);
  start();
}
