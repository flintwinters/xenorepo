import { useState } from "preact/hooks";
import { CommandButton } from "./command-button";

export interface ArrayTransferProps {
  id: string;
  label: string;
  description?: string;
  error?: string;
  disabled: boolean;
  choices: readonly string[];
  value: readonly string[];
  onChange: (value: string[]) => void;
}

const key = (value: string): string => value.toLocaleLowerCase();

export function ArrayTransfer({ id, label, description, error, disabled, choices, value,
  onChange }: ArrayTransferProps) {
  const [dragged, setDragged] = useState<string | null>(null);
  const selected = new Set(value.map(key));
  const available = choices.filter((choice) => !selected.has(key(choice)));
  const assign = (choice: string): void => {
    if (!selected.has(key(choice))) onChange([...value, choice]);
  };
  const remove = (choice: string): void => onChange(value.filter((item) => key(item) !== key(choice)));
  const drop = (event: DragEvent, destination: "available" | "selected"): void => {
    event.preventDefault();
    const choice = dragged || event.dataTransfer?.getData("text/plain");
    if (disabled || !choice) return;
    destination === "selected" ? assign(choice) : remove(choice);
    setDragged(null);
  };
  const token = (choice: string, destination: "available" | "selected") => <CommandButton
    type="button" appearance="subtle" disabled={disabled} draggable={!disabled}
    aria-label={`${destination === "selected" ? "Remove" : "Assign"} ${choice}`}
    onDragStart={(event) => { setDragged(choice); event.dataTransfer?.setData("text/plain", choice); }}
    onDragEnd={() => setDragged(null)} onClick={() => destination === "selected" ? remove(choice) : assign(choice)}>
    {choice}</CommandButton>;
  return <fieldset id={id} class="x-ui-array-transfer" aria-invalid={Boolean(error)}
    aria-describedby={error ? `${id}-error` : undefined}><legend>{label}</legend>
    {description && <small>{description}</small>}<div class="x-ui-array-transfer-groups">
      <div class="x-ui-array-transfer-group" aria-label={`Available ${label}`}
        onDragOver={(event) => event.preventDefault()} onDrop={(event) => drop(event, "available")}>
        <strong>AVAILABLE</strong><div>{available.length ? available.map((choice) => token(choice, "available")) :
          <span>All selected</span>}</div></div>
      <div class="x-ui-array-transfer-group" aria-label={`Selected ${label}`}
        onDragOver={(event) => event.preventDefault()} onDrop={(event) => drop(event, "selected")}>
        <strong>SELECTED</strong><div>{value.length ? value.map((choice) => token(choice, "selected")) :
          <span>Drop selections here</span>}</div></div>
    </div>{error && <small id={`${id}-error`} role="alert">{error}</small>}</fieldset>;
}
