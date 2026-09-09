# Operator credential setup

## Outcome

Complete the browser-only account setup that Xenorepo cannot perform itself. At
the end, Calendar Console can send mail through Amazon SES, and Dispatch Ledger
can create Stripe Checkout Sessions and authenticate Stripe webhook deliveries.

Do not paste a secret into chat, an issue, a commit, or a shell command. Put it
only in the ignored files named below. A secret is shown only once by AWS or SES;
if it is lost, delete or deactivate it and create another.

These instructions use Amazon SES as the SMTP provider because Xenorepo requires
ordinary authenticated STARTTLS SMTP. Another SMTP provider is compatible, but
its website-specific clicks and sending rules will differ.

## Values to decide before starting

Record these non-secret values:

- `AWS_REGION`: the Amazon SES region, for example `us-east-1`.
- `CALENDAR_EMAIL_FROM`: an address at a domain you control.
- `CALENDAR_EMAIL_TO`: the calendar owner's destination address.
- `PUBLIC_BASE_URL`: the eventual public Dispatch Ledger URL, with no trailing
  slash. A permanent Stripe webhook cannot be completed until this exists.
- Stripe mode: use **Test mode** until an end-to-end test passes; test and live
  credentials cannot be mixed.

## 1. SMTP through Amazon SES

SES identities and SMTP credentials are regional. Stay in `AWS_REGION` for every
step. SES SMTP credentials are not general AWS access keys.

### Verify the sender

1. Open [Amazon SES](https://console.aws.amazon.com/ses/) and confirm the region
   selector shows `AWS_REGION`.
2. In the left navigation, choose **Configuration** > **Identities**, then
   **Create identity**.
3. Prefer **Domain**. Enter the domain from `CALENDAR_EMAIL_FROM`, enable **Easy
   DKIM**, and choose **Create identity**.
4. If DNS is in Route 53 in the same account, accept **Publish DNS records**. If
   it is elsewhere, copy every displayed DKIM CNAME record into that DNS
   provider. Return to SES and wait for the identity status to become
   **Verified**.
5. For a quick test without domain DNS access, choose **Email address** instead,
   enter `CALENDAR_EMAIL_FROM`, choose **Create identity**, and click the link in
   the verification email.
6. If the SES **Account dashboard** says the account is in the sandbox, either
   repeat the email-address verification for `CALENDAR_EMAIL_TO`, or choose
   **Request production access** and complete AWS's use-case form. Sandbox SES
   cannot send to an arbitrary unverified recipient.

### Create the SMTP login

1. In SES, choose **SMTP settings** in the left navigation.
2. Copy the displayed **SMTP endpoint**. Choose **Create SMTP credentials**.
3. On the IAM page that opens, name the user `xenorepo-calendar-smtp` and choose
   **Create user**. Keep the generated send-only policy; do not reuse the AWS
   automation user.
4. Choose **Show** beside **SMTP password**. Keep this page open.
5. Create `apps/calendar/.env` and enter:

   ```dotenv
   CALENDAR_EMAIL_TO=<calendar owner's address>
   CALENDAR_EMAIL_FROM=<verified SES sender address>
   CALENDAR_SMTP_HOST=<SMTP endpoint copied from SES>
   CALENDAR_SMTP_PORT=587
   CALENDAR_SMTP_STARTTLS=true
   CALENDAR_SMTP_USERNAME=<SMTP username shown by SES>
   CALENDAR_SMTP_PASSWORD=<SMTP password shown by SES>
   ```

6. Confirm `apps/calendar/.env` is ignored, then close the credential page. Do
   not use port 465: Calendar Console currently implements STARTTLS, not implicit
   TLS.

## 2. Stripe test credentials and webhook

The app creates recurring Checkout Sessions with inline price data, so no Stripe
Product or Price ID is required. Begin in test mode. Repeat the procedure in live
mode only when the public deployment and test-mode acceptance check pass.

### Create the API key

1. Sign in to the [Stripe Dashboard](https://dashboard.stripe.com/).
2. Turn on **Test mode** (or choose a test sandbox) and verify the Dashboard is
   visibly in a test environment.
3. Choose **Developers** > **API keys**.
4. For the first integration checkpoint, reveal and copy the test **Secret key**
   beginning `sk_test_`. Never copy the publishable key; this backend does not
   use it. A restricted key can replace it after its exact permissions have been
   verified against the Checkout API calls.
5. Keep the value for the app file in the final subsection below.

### Create the public webhook endpoint

1. In the Stripe Dashboard test environment, choose **Developers** >
   **Webhooks** (in some Dashboard layouts this is **Workbench** > **Webhooks**).
2. Choose **Add destination** or **Add endpoint**.
3. Choose events from **Your account**, then select
   `checkout.session.completed`. This is the only event currently handled by the
   app.
4. Choose **Webhook endpoint** and set the endpoint URL to:

   ```text
   <PUBLIC_BASE_URL>/api/webhooks/payments/stripe
   ```

5. Add the description `Xenorepo Dispatch Ledger`, then choose **Create
   destination** or **Add endpoint**.
6. Open the new endpoint, find **Signing secret**, choose **Reveal**, and copy the
   value beginning `whsec_`. This secret belongs to this endpoint and mode; it is
   not an API key.

If `PUBLIC_BASE_URL` does not exist yet, stop here. For local development, use
the Stripe CLI forwarding workflow documented in `apps/mailing_list/SPEC.md`;
the CLI prints a temporary `whsec_` value. A Dashboard endpoint cannot deliver
to `localhost`.

### Store the pair

Create `apps/mailing_list/.env` and enter both values together:

```dotenv
MAILING_LIST_STRIPE_SECRET_KEY=<sk_test_... secret key>
MAILING_LIST_STRIPE_WEBHOOK_SECRET=<whsec_... endpoint signing secret>
```

Confirm the file is ignored. The app intentionally refuses to start if only one
of these values is present.

## Handoff checklist

The human setup is complete when all applicable boxes are true:

- [ ] `AWS_REGION` is selected and recorded.
- [ ] The SES sender identity shows **Verified** in the same region.
- [ ] The SES sandbox restriction is understood or production access is granted.
- [ ] The ignored Calendar `.env` contains all seven SMTP/email values.
- [ ] Stripe is in test mode and the API secret begins `sk_test_`.
- [ ] The Stripe endpoint URL is public HTTPS and its signing secret begins
      `whsec_`.
- [ ] The ignored mailing-list `.env` contains both Stripe values.
- [ ] `git status --short` does not list any `.env` file.

After this handoff, record only the non-secret region and public URL. Do not
transmit the secret values; automation can read the ignored files directly.

## Recovery and rotation

- SES SMTP: create replacement SMTP credentials, update Calendar's `.env`, verify
  delivery, then delete the old SMTP IAM user.
- Stripe API key: use **Developers** > **API keys** to roll or replace the key,
  then update the app file before expiring the old key.
- Stripe webhook: open the endpoint and roll its signing secret with an overlap
  period when Stripe offers one. The current app accepts one signing secret, so
  update it during the overlap and verify an event before the old secret expires.

## Authoritative references

- [Amazon SES identity verification](https://docs.aws.amazon.com/ses/latest/dg/creating-identities.html)
- [Amazon SES SMTP credentials](https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html)
- [Stripe API keys](https://docs.stripe.com/keys)
- [Stripe Checkout Sessions](https://docs.stripe.com/api/checkout/sessions)
