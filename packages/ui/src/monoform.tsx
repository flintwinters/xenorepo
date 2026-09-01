import type { JSX } from "preact";
import { useMemo, useState } from "preact/hooks";

export type MonoFormScalar = string | number | boolean | null;

export interface MonoFormSchema {
  type: "object" | "string" | "integer" | "number" | "boolean" | "array";
  format?: "date" | "date-time";
  title?: string;
  description?: string;
  enum?: MonoFormScalar[];
  nullable?: boolean;
  default?: unknown;
  minLength?: number;
  maxLength?: number;
  minimum?: number;
  maximum?: number;
  items?: MonoFormSchema;
  properties?: Record<string, MonoFormSchema>;
  required?: string[];
}

export interface MonoFormParameter {
  name: string;
  in: "path" | "query";
  required: boolean;
  schema: MonoFormSchema;
}

export interface MonoFormOperation {
  operationId: string;
  kind: "create" | "update" | "delete" | "action";
  entity: string;
  title: string;
  submitLabel: string;
  destructive: boolean;
  method: string;
  path: string;
  parameters: MonoFormParameter[];
  bodySchema: MonoFormSchema | null;
  successStatuses: number[];
}

export interface MonoFormManifest {
  schemaVersion: 1;
  application: { name: string; title: string };
  operations: MonoFormOperation[];
}

export interface MonoFormResult {
  operationId: string;
  status: number;
  data: unknown;
}

export interface MonoFormProps {
  manifest: MonoFormManifest;
  operationId: string;
  pathValues?: Record<string, string | number>;
  initialValues?: Record<string, unknown>;
  onSuccess?: (result: MonoFormResult) => void;
  onCancel?: () => void;
}

type Values = Record<string, unknown>;
type Errors = Record<string, string>;

const labelFor = (name: string, schema: MonoFormSchema): string =>
  schema.title || name.replaceAll("_", " ").replace(/^./, (value) => value.toUpperCase());

function initialBody(schema: MonoFormSchema | null, supplied: Values,
  parameters: MonoFormParameter[] = []): Values {
  const properties = { ...(schema?.properties || {}), ...Object.fromEntries(parameters
    .filter((parameter) => parameter.in === "query").map((parameter) => [parameter.name, parameter.schema])) };
  return Object.fromEntries(Object.entries(properties).map(([name, field]) =>
    [name, supplied[name] ?? field.default ?? (field.type === "boolean" ? false : "")]));
}

function valueFor(field: MonoFormSchema, raw: unknown): unknown {
  if (raw === "" && field.nullable) return null;
  if (field.type === "integer") return Number.parseInt(String(raw), 10);
  if (field.type === "number") return Number(raw);
  if (field.type === "array") return String(raw).split(",").map((value) => value.trim()).filter(Boolean);
  return raw;
}

function validate(schema: MonoFormSchema | null, values: Values): Errors {
  return Object.fromEntries(Object.entries(schema?.properties || {}).flatMap(([name, field]) => {
    const error = validateField(name, field, values[name], Boolean(schema?.required?.includes(name)));
    return error ? [[name, error]] : [];
  }));
}

function validateField(name: string, field: MonoFormSchema, raw: unknown, required: boolean): string {
  const label = labelFor(name, field);
  if (required && ["", null, undefined].includes(raw as null | undefined | string)) return `${label} is required`;
  if (typeof raw !== "string") return "";
  return lengthError(label, field, raw);
}

function lengthError(label: string, field: MonoFormSchema, raw: string): string {
  if (field.minLength !== undefined && raw.length < field.minLength)
    return `${label} must contain at least ${field.minLength} characters`;
  if (field.maxLength !== undefined && raw.length > field.maxLength)
    return `${label} cannot exceed ${field.maxLength} characters`;
  return "";
}

function fieldError(detail: unknown): Errors {
  if (!Array.isArray(detail)) return {};
  return Object.fromEntries(detail.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const value = item as { loc?: unknown[]; msg?: unknown };
    const name = value.loc?.at(-1);
    return typeof name === "string" && typeof value.msg === "string" ? [[name, value.msg]] : [];
  }));
}

function Field({ name, schema, value, error, disabled, onChange }: {
  name: string; schema: MonoFormSchema; value: unknown; error?: string; disabled: boolean;
  onChange: (value: unknown) => void;
}) {
  const common = { id: `monoform-${name}`, name, disabled, "aria-invalid": Boolean(error),
    "aria-describedby": error ? `monoform-${name}-error` : undefined };
  let control: JSX.Element;
  if (schema.type === "boolean") {
    control = <input {...common} type="checkbox" checked={Boolean(value)}
      onChange={(event) => onChange(event.currentTarget.checked)} />;
  } else if (schema.enum) {
    control = <select {...common} value={String(value ?? "")}
      onChange={(event) => onChange(event.currentTarget.value)}>
      {schema.nullable && <option value="">None</option>}
      {schema.enum.map((option) => <option value={String(option)}>{String(option)}</option>)}
    </select>;
  } else if (schema.type === "string" && schema.format === undefined && schema.maxLength
      && schema.maxLength > 160) {
    control = <textarea {...common} value={String(value ?? "")}
      onInput={(event) => onChange(event.currentTarget.value)} />;
  } else {
    const type = schema.type === "integer" || schema.type === "number" ? "number"
      : schema.format === "date-time" ? "datetime-local" : schema.format || "text";
    control = <input {...common} type={type} value={String(value ?? "")}
      min={schema.minimum} max={schema.maximum} minLength={schema.minLength} maxLength={schema.maxLength}
      onInput={(event) => onChange(event.currentTarget.value)} />;
  }
  return <label class="x-ui-monoform-field" for={`monoform-${name}`}>
    <span>{labelFor(name, schema)}</span>{control}
    {schema.description && <small>{schema.description}</small>}
    {error && <small id={`monoform-${name}-error`} role="alert">{error}</small>}
  </label>;
}

function requestPath(operation: MonoFormOperation, paths: Record<string, string | number>,
  values: Values): string {
  let path = operation.path;
  const query = new URLSearchParams();
  for (const parameter of operation.parameters) {
    const raw = parameter.in === "path" ? paths[parameter.name] : values[parameter.name];
    if (raw === undefined || raw === "") continue;
    if (parameter.in === "path") path = path.replace(`{${parameter.name}}`, encodeURIComponent(String(raw)));
    else query.set(parameter.name, String(raw));
  }
  return query.size ? `${path}?${query}` : path;
}

interface RequestOutcome { result?: MonoFormResult; errors: Errors; message: string }

function requestOptions(operation: MonoFormOperation, body: Values | undefined): RequestInit {
  return { method: operation.method, credentials: "same-origin",
    ...(body ? { headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : {}) };
}

function failureOutcome(data: unknown, status: number): RequestOutcome {
  const errors = fieldError((data as { detail?: unknown } | null)?.detail);
  const envelope = data as { error?: unknown; message?: unknown; detail?: unknown } | null;
  const fallback = envelope?.error || envelope?.message || envelope?.detail || `Request failed (${status})`;
  return { errors, message: Object.keys(errors).length ? "Review the marked fields." : String(fallback) };
}

async function execute(operation: MonoFormOperation, operationId: string,
  pathValues: Record<string, string | number>, values: Values): Promise<RequestOutcome> {
  const bodyProperties = Object.entries(operation.bodySchema?.properties || {});
  const body = operation.bodySchema ? Object.fromEntries(bodyProperties.map(([name, field]) =>
    [name, valueFor(field, values[name])])) : undefined;
  try {
    const response = await fetch(requestPath(operation, pathValues, values), requestOptions(operation, body));
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (response.ok) return { result: { operationId, status: response.status, data }, errors: {}, message: "" };
    return failureOutcome(data, response.status);
  } catch {
    return { errors: {}, message: "The service is unavailable. Try again." };
  }
}

function submissionErrors(operation: MonoFormOperation, pathValues: Record<string, string | number>,
  values: Values): Errors {
  const errors = validate(operation.bodySchema, values);
  for (const parameter of operation.parameters) {
    const value = parameter.in === "path" ? pathValues[parameter.name] : values[parameter.name];
    if (parameter.required && [undefined, ""].includes(value as undefined | string))
      errors[parameter.name] = `${parameter.name} is required`;
  }
  return errors;
}

export function MonoForm({ manifest, operationId, pathValues = {}, initialValues = {},
  onSuccess, onCancel }: MonoFormProps) {
  const operation = manifest.schemaVersion === 1
    ? manifest.operations.find((candidate) => candidate.operationId === operationId) : undefined;
  const [values, setValues] = useState<Values>(() => initialBody(
    operation?.bodySchema || null, initialValues, operation?.parameters));
  const [errors, setErrors] = useState<Errors>({});
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const properties = useMemo(() => Object.entries({ ...(operation?.bodySchema?.properties || {}),
    ...Object.fromEntries((operation?.parameters || []).filter((parameter) => parameter.in === "query")
      .map((parameter) => [parameter.name, parameter.schema])) }), [operation]);
  if (!operation || !operation.path.startsWith("/api/") || operation.path.includes("://")) {
    return <p role="alert">MonoForm operation is unavailable.</p>;
  }
  const submit = async (event: JSX.TargetedSubmitEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    if (pending || (operation.destructive && !confirmed)) return;
    const local = submissionErrors(operation, pathValues, values);
    if (Object.keys(local).length) { setErrors(local); return; }
    setPending(true); setErrors({}); setMessage("");
    const outcome = await execute(operation, operationId, pathValues, values);
    setErrors(outcome.errors); setMessage(outcome.message); setPending(false);
    if (outcome.result) onSuccess?.(outcome.result);
  };
  return <form class="x-ui-monoform" onSubmit={submit} noValidate>
    {properties.map(([name, schema]) => <Field name={name} schema={schema} value={values[name]}
      {...(errors[name] ? { error: errors[name] } : {})} disabled={pending}
      onChange={(value) => setValues({ ...values, [name]: value })} />)}
    {message && <p role="alert">{message}</p>}
    {operation.destructive && <label class="x-ui-monoform-confirm">
      <input type="checkbox" checked={confirmed} disabled={pending}
        onChange={(event) => setConfirmed(event.currentTarget.checked)} /> Confirm this destructive action
    </label>}
    <div class="x-ui-monoform-actions">
      <button type="submit" disabled={pending || (operation.destructive && !confirmed)}>
        {pending ? "Working…" : operation.submitLabel}
      </button>
      {onCancel && <button type="button" disabled={pending} onClick={onCancel}>Cancel</button>}
    </div>
  </form>;
}
