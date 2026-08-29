import { render } from "preact";
import { useEffect, useState } from "preact/hooks";
import {
  CommandButton,
  ConsolePane,
  ConsoleShell,
  StatusRail,
  UtilityRail,
} from "@xenorepo/ui";
import { checkout, offering } from "./client.js";
import "./styles.css";

type Offering = Awaited<ReturnType<typeof offering>>;

function Enrollment() {
  const [details, setDetails] = useState<Offering>();
  const [message, setMessage] = useState("");

  useEffect(() => { void offering().then(setDetails); }, []);

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const email = new FormData(form).get("email");
    if (typeof email !== "string") return;
    setMessage("CREATING SECURE CHECKOUT…");
    try {
      const result = await checkout(email);
      setMessage(`CHECKOUT ${result.checkout_id} READY VIA ${result.provider.toUpperCase()}`);
      if (result.checkout_url.startsWith("http")) location.assign(result.checkout_url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "CHECKOUT FAILED");
    }
  }

  const price = details
    ? new Intl.NumberFormat(undefined, { style: "currency", currency: details.currency })
      .format(details.amount_minor / 100)
    : "—";
  return <ConsoleShell class="mailing-frame"
    header={<UtilityRail><strong>DISPATCH LEDGER</strong><span>PAID SUBSCRIBER INTAKE</span></UtilityRail>}
    footer={<StatusRail><span class="mailing-indicator"><i /><span role="status">
      PAYMENT GATEWAY READY
    </span></span></StatusRail>}>
    <section class="mailing-body">
      <ConsolePane title="MEMBERSHIP" tone="green"><div class="mailing-card">
        <strong>Independent dispatch</strong>
        <div class="mailing-price">{price} / {details?.interval ?? "month"}</div>
        <form id="enroll" onSubmit={submit}>
          <label>Email address<input name="email" type="email" required autoComplete="email" maxLength={320} /></label>
          <CommandButton id="submit" type="submit">CONTINUE TO PAYMENT</CommandButton>
        </form>
        <div id="message" class="mailing-message" role="status" aria-live="polite">{message}</div>
      </div></ConsolePane>
    </section>
  </ConsoleShell>;
}

export function mount(root: HTMLElement): void {
  render(<Enrollment />, root);
}
