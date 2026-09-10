import type { ComponentChildren } from "preact";
import { useState } from "preact/hooks";
import { CommandButton, Form, FormActions, FormField, FormInput, FormSelect, FormTextarea } from "monoui";
import { createCard, createColumn, createTag, editAttachment, editBoardDetails, editCard, editColumn,
  setTagColor, type Attachment, type Card, type Column } from "./client.js";

interface Common { onCancel: () => void; onSaved: () => void }
const value = (data: FormData, name: string): string => String(data.get(name) ?? "").trim();

function OwnedForm({ submit, children, onCancel, submitLabel = "SAVE" }: Common & {
  submit: (data: FormData) => Promise<void>; children: ComponentChildren; submitLabel?: string }) {
  const [pending, setPending] = useState(false), [error, setError] = useState("");
  const perform = async (event: SubmitEvent): Promise<void> => {
    event.preventDefault(); setPending(true); setError("");
    try { await submit(new FormData(event.currentTarget as HTMLFormElement)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Request failed"); setPending(false); }
  };
  return <Form onSubmit={perform} noValidate><fieldset disabled={pending}>{children}</fieldset>
    {error && <p role="alert">{error}</p>}<FormActions><CommandButton type="submit" disabled={pending}>
      {pending ? "SAVING…" : submitLabel}</CommandButton><CommandButton type="button" appearance="subtle"
      disabled={pending} onClick={onCancel}>CANCEL</CommandButton></FormActions></Form>;
}
const textField = (name: string, label: string, initial = "", type = "text") =>
  <FormField label={label} controlId={`kanban-${name}`}><FormInput id={`kanban-${name}`} name={name}
    type={type} value={initial} required maxLength={120} /></FormField>;

export function BoardForm({ board, ...common }: Common & { board: { name: string; description: string } }) {
  return <OwnedForm {...common} submit={async (data) => { await editBoardDetails({ name: value(data, "name"),
    description: value(data, "description") }); common.onSaved(); }}>{textField("name", "Name", board.name)}
    <FormField label="Description" controlId="kanban-description"><FormTextarea id="kanban-description"
      name="description" maxLength={4000} value={board.description} /></FormField></OwnedForm>;
}
export function ColorForm({ tag, color, ...common }: Common & { tag: string; color: string }) {
  return <section><h3>{`Tag “${tag}”`}</h3><OwnedForm {...common} submitLabel="SAVE COLOR" submit={async (data) => {
    await setTagColor(tag, value(data, "color")); common.onSaved(); }}>
    <FormField label="Tag color" controlId={`kanban-color-${tag}`}><FormInput id={`kanban-color-${tag}`}
      name="color" value={color} required maxLength={7} /></FormField></OwnedForm></section>;
}
export function ColumnForm({ column, ...common }: Common & { column: Column | null }) {
  return <OwnedForm {...common} submitLabel={column ? "SAVE" : "CREATE"} submit={async (data) => {
    const name = value(data, "name"), color = value(data, "color");
    if (column) await editColumn(column.id, name, color); else await createColumn(name, color); common.onSaved(); }}>
    {textField("name", "Column name", column?.name)}
    {textField("color", "Column color", column?.color ?? "#665c54")}</OwnedForm>;
}
export function TagForm({ color, ...common }: Common & { color: string }) {
  return <OwnedForm {...common} submitLabel="CREATE" submit={async (data) => {
    await createTag(value(data, "name"), value(data, "color")); common.onSaved(); }}>
    {textField("name", "Tag name")}{textField("color", "Tag color", color)}</OwnedForm>;
}
export function AttachmentForm({ attachment, ...common }: Common & { attachment: Attachment }) {
  return <OwnedForm {...common} submit={async (data) => { await editAttachment(attachment.id, value(data, "title"),
    attachment.kind === "link" ? value(data, "url") : undefined); common.onSaved(); }}>
    {textField("title", "Attachment title", attachment.title)}{attachment.kind === "link" &&
      textField("url", "Web address", attachment.url ?? "", "url")}</OwnedForm>;
}
export function CardForm({ card, columnId, choices, ...common }: Common & { card: Card | null;
  columnId: string; choices: string[] }) {
  return <OwnedForm {...common} submit={async (data) => { const fields = { title: value(data, "title"),
    tags: card ? data.getAll("tags").map(String) : value(data, "tags").split(",")
      .map((tag) => tag.trim()).filter(Boolean) }; if (card) await editCard(card.id, fields);
    else await createCard(columnId, fields); common.onSaved(); }}>{textField("title", "Title", card?.title)}
    {card ? <FormField label="Tags" controlId="kanban-tags" description="Use Ctrl/Cmd to select multiple">
      <FormSelect id="kanban-tags" name="tags" multiple>{choices.map((tag) =>
        <option value={tag} selected={card.tags.includes(tag)}>{tag}</option>)}</FormSelect></FormField> :
      <FormField label="Tags" controlId="kanban-tags" description="Comma-separated"><FormInput
        id="kanban-tags" name="tags" /></FormField>}</OwnedForm>;
}
