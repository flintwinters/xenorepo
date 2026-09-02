import type { ComponentChildren, JSX } from "preact";
import { useEffect } from "preact/hooks";
import "./styles.css";

export { MonoForm } from "./monoform";
export type { MonoFormManifest, MonoFormOperation, MonoFormProps, MonoFormResult } from "./monoform";
export { CommandButton } from "./command-button";
export type { CommandButtonProps } from "./command-button";
export {
  Form, FormActions, FormConfirmation, FormField, FormInput, FormSelect, FormTextarea,
} from "./form-controls";

type Tone = "blue" | "green" | "orange" | "purple" | "neutral";
type DivProps = JSX.HTMLAttributes<HTMLDivElement>;

const classes = (...values: Array<string | undefined>): string => values.filter(Boolean).join(" ");

interface ShellProps extends DivProps {
  header?: ComponentChildren;
  footer?: ComponentChildren;
}

export function ConsoleShell({ header, footer, children, class: className, ...props }: ShellProps) {
  return <div class={classes("x-ui-shell", className as string | undefined)} {...props}>
    <header>{header}</header><main>{children}</main><footer>{footer}</footer>
  </div>;
}

export function ConsoleWorkspace({ class: className, ...props }: DivProps) {
  return <div class={classes("x-ui-workspace", className as string | undefined)} {...props} />;
}

export function UtilityRail({ class: className, ...props }: DivProps) {
  return <div class={classes("x-ui-rail", className as string | undefined)} {...props} />;
}

export function StatusRail({ class: className, ...props }: DivProps) {
  return <UtilityRail class={classes("x-ui-status-rail", className as string | undefined)} {...props} />;
}

interface PaneProps extends Omit<JSX.HTMLAttributes<HTMLElement>, "title"> {
  title: ComponentChildren;
  titleEnd?: ComponentChildren;
  tone?: Tone;
  contentHeight?: boolean;
  chromeProps?: JSX.HTMLAttributes<HTMLDivElement>;
}

export function ConsolePane({ title, titleEnd, tone = "blue", contentHeight = false, chromeProps,
  children, class: className, ...props }: PaneProps) {
  return <section class={classes("x-ui-pane", contentHeight ? "x-ui-pane-content-height" : undefined,
    `x-ui-tone-${tone}`, className as string | undefined)} {...props}>
    <div class="x-ui-chrome" {...chromeProps}>
      <span>{title}</span><span class="x-ui-title-end">{titleEnd}</span>
    </div>
    <div class="x-ui-pane-body">{children}</div>
  </section>;
}

interface EmptyStateProps extends DivProps {
  heading?: ComponentChildren;
  detail?: ComponentChildren;
}

export function EmptyState({ heading = "NO RECORDS", detail, class: className,
  ...props }: EmptyStateProps) {
  return <div class={classes("x-ui-empty-state", className as string | undefined)} {...props}>
    <strong>{heading}</strong>{detail && <p>{detail}</p>}
  </div>;
}

interface ModalProps extends Omit<DivProps, "onClick"> {
  labelledBy: string;
  onDismiss: () => void;
  contentClass?: string;
}

export function Modal({ labelledBy, onDismiss, contentClass, class: className,
  children, ...props }: ModalProps) {
  useEffect(() => {
    const dismissOnEscape = (event: KeyboardEvent): void => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      onDismiss();
    };
    window.addEventListener("keydown", dismissOnEscape);
    return () => window.removeEventListener("keydown", dismissOnEscape);
  }, [onDismiss]);
  return <div class={classes("x-ui-modal-backdrop", className as string | undefined)}
    onClick={(event) => {
      if (event.target === event.currentTarget) onDismiss();
    }} {...props}>
    <section class={classes("x-ui-modal-content", contentClass)} role="dialog" aria-modal="true"
      aria-labelledby={labelledBy}>{children}</section>
  </div>;
}
