import type { ComponentChildren, JSX } from "preact";


type FormProps = JSX.HTMLAttributes<HTMLFormElement>;
type InputProps = JSX.InputHTMLAttributes<HTMLInputElement>;
type SelectProps = JSX.SelectHTMLAttributes<HTMLSelectElement>;
type TextareaProps = JSX.TextareaHTMLAttributes<HTMLTextAreaElement>;

export function Form({ class: className, ...props }: FormProps) {
  const classes = ["x-ui-form", className].filter(Boolean).join(" ");
  return <form class={classes} {...props} />;
}

export function FormField({ label, controlId, description, error, children }: {
  label: ComponentChildren;
  controlId: string;
  description?: ComponentChildren;
  error?: ComponentChildren;
  children: ComponentChildren;
}) {
  return <label class="x-ui-form-field" for={controlId}>
    <span>{label}</span>{children}
    {description && <small>{description}</small>}
    {error && <small id={`${controlId}-error`} role="alert">{error}</small>}
  </label>;
}

export function FormInput(props: InputProps) {
  return <input class="x-ui-form-control" {...props} />;
}

export function FormSelect(props: SelectProps) {
  return <select class="x-ui-form-control" {...props} />;
}

export function FormTextarea(props: TextareaProps) {
  return <textarea class="x-ui-form-control" {...props} />;
}

export function FormConfirmation({ children, ...props }: InputProps) {
  return <label class="x-ui-form-confirm">
    <FormInput type="checkbox" {...props} /> {children}
  </label>;
}

export function FormActions({ children }: { children: ComponentChildren }) {
  return <div class="x-ui-form-actions">{children}</div>;
}
