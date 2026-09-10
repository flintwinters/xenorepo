import type { ComponentChildren, JSX } from "preact";

export interface TableColumn<Row> {
  key: string;
  header: ComponentChildren;
  width: string;
  render: (row: Row) => ComponentChildren;
  rowHeader?: boolean;
  class?: string;
}

export interface TableProps<Row> extends Omit<JSX.HTMLAttributes<HTMLTableElement>, "children"> {
  columns: readonly TableColumn<Row>[];
  rows: readonly Row[];
  rowKey: (row: Row) => string | number;
  caption?: ComponentChildren;
}

const classes = (...values: Array<string | undefined>): string => values.filter(Boolean).join(" ");

/** Accessible, view-only tabular structure. Data operations remain with the consumer. */
export function Table<Row>({ columns, rows, rowKey, caption, class: className,
  ...props }: TableProps<Row>) {
  return <div class="x-ui-table-scroll"><table class={classes("x-ui-table", className as string | undefined)}
    {...props}>
    {caption && <caption>{caption}</caption>}
    <colgroup>{columns.map((column) => <col key={column.key} class={column.class}
      style={{ width: column.width }} />)}</colgroup>
    <thead><tr>{columns.map((column) => <th key={column.key} scope="col" class={column.class}>
      {column.header}
    </th>)}</tr></thead>
    <tbody>{rows.map((row) => <tr key={rowKey(row)}>{columns.map((column) => {
      const Tag = column.rowHeader ? "th" : "td";
      return <Tag key={column.key} scope={column.rowHeader ? "row" : undefined} class={column.class}>
        {column.render(row)}
      </Tag>;
    })}</tr>)}</tbody>
  </table></div>;
}
