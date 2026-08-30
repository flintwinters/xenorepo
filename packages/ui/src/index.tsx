import type { ComponentChildren, JSX } from "preact";
import "./styles.css";

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
}

export function ConsolePane({ title, titleEnd, tone = "blue", contentHeight = false, children,
  class: className, ...props }: PaneProps) {
  return <section class={classes("x-ui-pane", contentHeight ? "x-ui-pane-content-height" : undefined,
    `x-ui-tone-${tone}`, className as string | undefined)} {...props}>
    <div class="x-ui-chrome"><span>{title}</span><span class="x-ui-title-end">{titleEnd}</span></div>
    <div class="x-ui-pane-body">{children}</div>
  </section>;
}

interface CommandButtonProps extends JSX.ButtonHTMLAttributes<HTMLButtonElement> {
  pressed?: boolean;
  appearance?: "default" | "subtle";
}

export function CommandButton({ pressed = false, appearance = "default", class: className,
  children, ...props }: CommandButtonProps) {
  return <span class={classes("x-ui-command", `x-ui-command-${appearance}`, className as string | undefined)}>
    <button class="x-ui-command-control" aria-pressed={pressed} {...props}>{children}</button>
  </span>;
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
