import { render } from "preact";
import { useEffect, useState } from "preact/hooks";
import {
  CommandButton,
  ConsolePane,
  ConsoleShell,
  ConsoleWorkspace,
  StatusRail,
  UtilityRail,
} from "@xenorepo/ui";
import { checkout, checkoutStatus, offering, settleSandbox } from "./client.js";
import "./styles.css";

type Offering = Awaited<ReturnType<typeof offering>>;
type Receipt = Awaited<ReturnType<typeof checkoutStatus>>;
type CheckoutPhase = "loading" | "ready" | "creating" | "awaiting" | "settling" | "active" | "cancelled" | "failed";

const phaseLabel: Record<CheckoutPhase, string> = {
  loading: "LOADING OFFER",
  ready: "CHECKOUT READY",
  creating: "OPENING CHECKOUT",
  awaiting: "PAYMENT PENDING",
  settling: "CONFIRMING PAYMENT",
  active: "SUBSCRIPTION ACTIVE",
  cancelled: "CHECKOUT CANCELLED",
  failed: "ACTION REQUIRED",
};

function Enrollment() {
  const [details, setDetails] = useState<Offering>();
  const [message, setMessage] = useState("Loading current membership terms…");
  const [sandboxCheckout, setSandboxCheckout] = useState<string>();
  const [receipt, setReceipt] = useState<Receipt>();
  const [phase, setPhase] = useState<CheckoutPhase>("loading");

  useEffect(() => {
    void offering().then((result) => {
      setDetails(result);
      const query = new URLSearchParams(location.search);
      const checkoutResult = query.get("checkout");
      const sessionId = query.get("session_id");
      if (checkoutResult === "cancelled") {
        setPhase("cancelled"); setMessage("Checkout cancelled. No payment was taken.");
      } else if (checkoutResult === "success" && sessionId) {
        setPhase("settling"); setMessage("Confirming your subscription…");
        void resolveReturn(sessionId);
      } else {
        setPhase("ready"); setMessage("Secure enrollment is ready.");
      }
    }).catch((error) => {
      setPhase("failed");
      setMessage(error instanceof Error ? error.message : "Unable to load membership terms.");
    });
  }, []);

  async function resolveReturn(sessionId: string) {
    try {
      for (let attempt = 0; attempt < 6; attempt += 1) {
        const result = await checkoutStatus(sessionId);
        setReceipt(result);
        if (result.state === "paid") {
          setPhase("active"); setMessage("SUBSCRIPTION ACTIVE"); return;
        }
        if (result.state === "failed" || result.state === "cancelled") {
          setPhase(result.state); setMessage(`CHECKOUT ${result.state.toUpperCase()}`); return;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 500));
      }
      setPhase("awaiting");
      setMessage("Payment received; activation is still pending. Refresh to check again.");
    } catch (error) {
      setPhase("failed");
      setMessage(error instanceof Error ? error.message : "Unable to confirm checkout.");
    }
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const email = new FormData(form).get("email");
    if (typeof email !== "string") return;
    setPhase("creating"); setMessage("Creating a secure checkout…");
    try {
      const result = await checkout(email);
      setPhase("awaiting"); setMessage(`Checkout ready via ${result.provider}.`);
      if (result.checkout_url.startsWith("http")) location.assign(result.checkout_url);
      else setSandboxCheckout(result.checkout_id);
    } catch (error) {
      setPhase("failed");
      setMessage(error instanceof Error ? error.message : "CHECKOUT FAILED");
    }
  }

  async function settle(state: "paid" | "cancelled") {
    if (!sandboxCheckout) return;
    setPhase("settling");
    setMessage(state === "paid" ? "Confirming payment…" : "Cancelling checkout…");
    try {
      const result = await settleSandbox(sandboxCheckout, state);
      const paid = result.state === "paid";
      setReceipt(result);
      setPhase(paid ? "active" : "cancelled");
      setMessage(paid ? "SUBSCRIPTION ACTIVE" : "CHECKOUT CANCELLED");
      const query = paid ? `?checkout=success&session_id=${encodeURIComponent(result.checkout_id)}`
        : "?checkout=cancelled";
      history.replaceState(null, "", query);
      setSandboxCheckout(undefined);
    } catch (error) {
      setPhase("failed");
      setMessage(error instanceof Error ? error.message : "CHECKOUT UPDATE FAILED");
    }
  }

  const price = details
    ? new Intl.NumberFormat(undefined, { style: "currency", currency: details.currency })
      .format(details.amount_minor / 100)
    : "—";
  const busy = phase === "loading" || phase === "creating" || phase === "settling";
  const statusTone = phase === "failed" || phase === "cancelled" ? "warning" : phase === "active" ? "active" : "ready";
  return <ConsoleShell class="mailing-frame"
    header={<UtilityRail class="mailing-header"><strong>DISPATCH LEDGER</strong>
      <span>VOL. 01 / INDEPENDENT CORRESPONDENCE</span><span class="mailing-header-end">MONTHLY</span>
    </UtilityRail>}
    footer={<StatusRail><span class={`mailing-indicator ${statusTone}`}><i /><span role="status">
      {phaseLabel[phase]}
    </span></span><span class="mailing-footer-note">NO ADS · CANCEL ANY TIME</span></StatusRail>}>
    <ConsoleWorkspace class="mailing-body" aria-labelledby="mailing-title">
      <div class="mailing-editorial">
        <p class="mailing-kicker">A MONTHLY FIELD LETTER</p>
        <h1 id="mailing-title">Reporting for people who still read past the headline.</h1>
        <p class="mailing-deck">One considered dispatch each month: independent reporting,
          annotated sources, and a clear account of what changed.</p>
        <div class="mailing-rule"><span>IN EACH EDITION</span></div>
        <ul class="mailing-manifest">
          <li><strong>01</strong><span><b>One durable argument</b>
            Built to remain useful after the news cycle.</span></li>
          <li><strong>02</strong><span><b>Primary sources</b>Links, notes, and uncertainty included.</span></li>
          <li><strong>03</strong><span><b>Reader-supported</b>No sponsors, tracking pitches, or filler.</span></li>
        </ul>
      </div>
      <ConsolePane class="mailing-membership" title="MEMBERSHIP DESK" tone="green"
        titleEnd={<span>{details?.payment_provider?.toUpperCase() ?? "CONNECTING"}</span>}>
        <div class="mailing-card">
          <div><p class="mailing-eyebrow">FOUNDING READER RATE</p>
            <strong class="mailing-offer">Independent dispatch</strong></div>
          <div class="mailing-price"><span>{price}</span><small> / {details?.interval ?? "month"}</small></div>
          <p class="mailing-terms">One edition every month. Your membership funds the reporting
            directly and can be cancelled at any time.</p>
          {phase === "active" ? <section class="mailing-confirmation" aria-labelledby="confirmation-title">
            <p class="mailing-confirmation-mark" aria-hidden="true">✓</p>
            <div><p class="mailing-eyebrow">PAYMENT CONFIRMED</p>
              <h2 id="confirmation-title">You’re on the ledger.</h2></div>
            <dl><div><dt>MEMBERSHIP</dt><dd>Independent dispatch</dd></div>
              <div><dt>RENEWS</dt><dd>{price} / {details?.interval ?? "month"}</dd></div>
              <div><dt>STATUS</dt><dd>Active</dd></div>
              <div><dt>PROVIDER</dt><dd>{receipt?.provider.toUpperCase() ?? "CONFIRMED"}</dd></div>
              <div><dt>WEBHOOK</dt><dd>{receipt ? `${receipt.event_count} signed event stored` : "Recorded"}</dd></div>
              <div><dt>ACTIVATED</dt><dd>{receipt?.paid_at
                ? new Date(receipt.paid_at).toLocaleString() : "Just now"}</dd></div>
              <div><dt>REFERENCE</dt><dd>{receipt?.checkout_id.slice(-12) ?? "Available after refresh"}</dd></div>
            </dl>
            <p>Your subscription is recorded. Edition delivery will become available with the
              upcoming mail-service checkpoint.</p>
          </section> : <form id="enroll" onSubmit={submit}>
              <label for="email">Email address</label>
              <input id="email" name="email" type="email" required autoComplete="email" maxLength={320}
                placeholder="reader@example.com" disabled={busy} />
              <CommandButton id="submit" type="submit" disabled={!details || busy}>
                {phase === "creating" ? "OPENING…" : "CONTINUE TO PAYMENT"}
              </CommandButton>
            </form>}
          {sandboxCheckout && <div class="mailing-actions" aria-label="Sandbox checkout controls">
            <p>LOCAL CHECKOUT PREVIEW</p>
            <CommandButton type="button" disabled={busy} onClick={() => void settle("paid")}>
              COMPLETE SANDBOX PAYMENT
            </CommandButton>
            <CommandButton type="button" appearance="subtle" disabled={busy}
              onClick={() => void settle("cancelled")}>CANCEL</CommandButton>
          </div>}
          <div id="message" class={`mailing-message ${statusTone}`} role="status" aria-live="polite">
            <i /> <span>{message}</span>
          </div>
          <p class="mailing-assurance">SECURE CHECKOUT · EMAIL USED ONLY FOR DELIVERY</p>
        </div>
      </ConsolePane>
    </ConsoleWorkspace>
  </ConsoleShell>;
}

export function mount(root: HTMLElement): void {
  render(<Enrollment />, root);
}
