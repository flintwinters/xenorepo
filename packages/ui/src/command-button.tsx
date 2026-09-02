import type { JSX } from "preact";


export interface CommandButtonProps extends JSX.ButtonHTMLAttributes<HTMLButtonElement> {
  pressed?: boolean;
  appearance?: "default" | "subtle";
}

const classes = (...values: Array<string | undefined>): string => values.filter(Boolean).join(" ");

export function CommandButton({ pressed, appearance = "default", class: className,
  children, ...props }: CommandButtonProps) {
  return <span class={classes("x-ui-command", `x-ui-command-${appearance}`,
    className as string | undefined)}>
    <button class="x-ui-command-control" {...(pressed === undefined ? {} : { "aria-pressed": pressed })}
      {...props}>{children}</button>
  </span>;
}
