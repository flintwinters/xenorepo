import { useState } from "preact/hooks";
import { CommandButton, Form, FormActions, FormConfirmation, FormField, FormInput } from "monoui";
import { deleteContact, saveContact, type Contact, type ContactFields } from "./client.js";

export function ContactForm({ contact, onCancel, onChanged }: { contact: Contact | null;
  onCancel: () => void; onChanged: () => void }) {
  const [pending, setPending] = useState(false), [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const submit = async (event: SubmitEvent): Promise<void> => {
    event.preventDefault(); setPending(true); setError("");
    const data = new FormData(event.currentTarget as HTMLFormElement), value = (name: string) =>
      String(data.get(name) ?? "").trim();
    const optional = (name: string): string | null => value(name) || null;
    const body: ContactFields = { name: value("name"), email: value("email"), phone: optional("phone"),
      company: optional("company"), job_title: optional("job_title"), city: optional("city"),
      tags: value("tags").split(",").map((tag) => tag.trim()).filter(Boolean) };
    try { await saveContact(contact?.id ?? null, body); onChanged(); }
    catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save contact"); setPending(false);
    }
  };
  const remove = async (): Promise<void> => {
    if (!contact || !confirmed) return; setPending(true); setError("");
    try { await deleteContact(contact.id); onChanged(); }
    catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete contact"); setPending(false);
    }
  };
  const fields = [["name", "Name", "text", true], ["email", "Email", "email", true],
    ["phone", "Phone", "text", false], ["company", "Company", "text", false],
    ["job_title", "Job title", "text", false], ["city", "City", "text", false]] as const;
  return <><Form onSubmit={submit} noValidate>{fields.map(([name, label, type, required]) =>
    <FormField label={label} controlId={`contact-${name}`}><FormInput id={`contact-${name}`} name={name}
      type={type} required={required} maxLength={name === "email" ? 254 : 160}
      value={contact?.[name] ?? ""} disabled={pending} /></FormField>)}
    <FormField label="Tags" controlId="contact-tags" description="Comma-separated"><FormInput
      id="contact-tags" name="tags" value={contact?.tags.join(", ") ?? ""} disabled={pending} /></FormField>
    {error && <p role="alert">{error}</p>}<FormActions><CommandButton type="submit" disabled={pending}>
      {pending ? "SAVING…" : contact ? "SAVE" : "CREATE"}</CommandButton><CommandButton type="button"
      appearance="subtle" disabled={pending} onClick={onCancel}>CANCEL</CommandButton></FormActions></Form>
    {contact && <section><FormConfirmation checked={confirmed} disabled={pending}
      onChange={(event) => setConfirmed(event.currentTarget.checked)}>
        Confirm this destructive action
      </FormConfirmation>
      <CommandButton class="danger" disabled={pending || !confirmed} onClick={() => void remove()}>
        DELETE</CommandButton></section>}</>;
}
