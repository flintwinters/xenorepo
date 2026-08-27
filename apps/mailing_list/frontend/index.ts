/** Paid mailing-list enrollment using central Lit UI components. */
import { html, render } from "lit";
import "@xenorepo/lit-ui";

type Offering = { amount_minor: number; currency: string; interval: string; payment_provider: string };

export async function mount(root: HTMLElement): Promise<void> {
  const offering = await fetch("/api/offering").then(response => response.json()) as Offering;
  const price = new Intl.NumberFormat(undefined, { style: "currency", currency: offering.currency }).format(offering.amount_minor / 100);
  render(html`<style>
    *{box-sizing:border-box}.frame{height:100%;display:grid;grid-template-rows:28px 1fr 24px}.body{display:grid;place-items:center;padding:20px}.card{width:min(460px,100%);display:grid;gap:14px;padding:20px}.price{font-size:32px;color:#b8bb26}form{display:grid;gap:10px}label{display:grid;gap:4px}input{padding:9px;color:#ebdbb2;background:#181a1b;border:1px solid #665c54}.message{min-height:20px;color:#fabd2f}
  </style><x-console-shell class="frame"><x-utility-rail slot="header"><strong>DISPATCH LEDGER</strong><span>PAID SUBSCRIBER INTAKE</span></x-utility-rail><section class="body"><x-console-pane title="MEMBERSHIP" tone="green"><div class="card"><strong>Independent dispatch</strong><div class="price">${price} / ${offering.interval}</div><form id="enroll"><label>Email address<input id="email" type="email" required autocomplete="email" maxlength="320"></label><x-command-button id="submit">CONTINUE TO PAYMENT</x-command-button></form><div id="message" class="message" role="status" aria-live="polite"></div></div></x-console-pane></section><x-status-rail slot="footer"><x-status-indicator label="PAYMENT GATEWAY READY"></x-status-indicator></x-status-rail></x-console-shell>`, root);
  const form = root.querySelector<HTMLFormElement>("#enroll")!;
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const message = root.querySelector<HTMLElement>("#message")!;
    const email = root.querySelector<HTMLInputElement>("#email")!.value;
    message.textContent = "CREATING SECURE CHECKOUT…";
    const response = await fetch("/api/checkouts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
    const result = await response.json();
    if (!response.ok) { message.textContent = result.error ?? "CHECKOUT FAILED"; return; }
    message.textContent = `CHECKOUT ${result.checkout_id} READY VIA ${result.provider.toUpperCase()}`;
    if (result.checkout_url.startsWith("http")) location.assign(result.checkout_url);
  });
  root.querySelector("#submit")!.addEventListener("click", () => form.requestSubmit());
}
