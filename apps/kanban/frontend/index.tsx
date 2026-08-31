import { Component, render } from "preact";
import { CommandButton, ConsolePane, ConsoleShell, EmptyState, StatusRail, UtilityRail } from "@xenorepo/ui";
import {
  addComment, addLink, addUpload, createCard, createColumn, editAttachment, editBoard,
  editCard, editColumn, editComment, loadBoard, moveCard, moveColumn, setArchived,
  type Attachment, type Card, type CardFields, type Comment, type KanbanView,
} from "./client.js";
import "./styles.css";

type Mode = "board" | "archive" | "activity";
interface State {
  view: KanbanView | null;
  mode: Mode;
  selected: string | null;
  creatingIn: string | null;
  editingBoard: boolean;
  message: string;
  failed: boolean;
  busy: boolean;
}

const labels = (value: FormDataEntryValue | null): string[] => String(value ?? "")
  .split(",").map((item) => item.trim()).filter(Boolean);
const active = <T extends { archived_at?: string | null }>(values: T[]): T[] =>
  values.filter((value) => !value.archived_at);

class KanbanBoard extends Component<Record<string, never>, State> {
  override state: State = { view: null, mode: "board", selected: null, creatingIn: null,
    editingBoard: false, message: "Loading board…", failed: false, busy: false };
  private dragged: string | null = null;

  override componentDidMount(): void { void this.refresh("Board ready"); }
  private refresh = async (message?: string): Promise<void> => {
    try {
      const view = await loadBoard();
      this.setState({ view, message: message ?? this.state.message, failed: false, busy: false });
    } catch (error) {
      this.setState({ message: error instanceof Error ? error.message : "Unexpected error",
        failed: true, busy: false });
    }
  };
  private perform = (message: string, action: () => Promise<void>): void => {
    this.setState({ busy: true });
    void action().then(() => this.refresh(message)).catch((error) => this.setState({
      message: error instanceof Error ? error.message : "Unexpected error", failed: true, busy: false,
    }));
  };
  private card(id: string | null): Card | null {
    return this.state.view?.cards.find((value) => value.id === id) ?? null;
  }
  private cards(columnId: string): Card[] {
    return active(this.state.view?.cards ?? []).filter((value) => value.column_id === columnId)
      .sort((a, b) => a.position - b.position);
  }
  private saveBoard = (event: SubmitEvent): void => {
    event.preventDefault();
    const data = new FormData(event.currentTarget as HTMLFormElement);
    this.perform("Board details updated", async () => {
      await editBoard(String(data.get("name")), String(data.get("description")));
      this.setState({ editingBoard: false });
    });
  };
  private saveCard = (event: SubmitEvent): void => {
    event.preventDefault();
    const data = new FormData(event.currentTarget as HTMLFormElement), existing = this.card(this.state.selected);
    const fields: CardFields = { title: String(data.get("title")),
      description: String(data.get("description")), assignee: String(data.get("assignee")),
      labels: labels(data.get("labels")), priority: String(data.get("priority")) as CardFields["priority"] };
    this.perform(existing ? "Card updated" : "Card created", async () => {
      if (existing) await editCard(existing.id, fields);
      else await createCard(this.state.creatingIn!, fields);
      this.setState({ selected: null, creatingIn: null });
    });
  };
  private createColumn = (): void => {
    const name = window.prompt("Column name");
    if (name) this.perform("Column created", () => createColumn(name));
  };
  private renameColumn = (id: string, current: string): void => {
    const name = window.prompt("Column name", current);
    if (name && name !== current) this.perform("Column renamed", () => editColumn(id, name));
  };
  private archive = (kind: string, id: string, name: string): void => {
    if (window.confirm(`Archive “${name}”?`)) {
      if (kind === "card") this.setState({ selected: null });
      this.perform(`${kind} archived`, () => setArchived(kind, id));
    }
  };
  private drop = (event: DragEvent, columnId: string): void => {
    event.preventDefault();
    if (!this.dragged) return;
    const id = this.dragged, position = this.cards(columnId).length;
    this.dragged = null;
    this.perform("Card moved", () => moveCard(id, columnId, position));
  };
  private saveComment = (event: SubmitEvent, cardId: string): void => {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement, body = String(new FormData(form).get("body"));
    this.perform("Comment added", async () => { await addComment(cardId, body); form.reset(); });
  };
  private saveLink = (event: SubmitEvent, cardId: string): void => {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement, data = new FormData(form);
    this.perform("Link attached", async () => {
      await addLink(cardId, String(data.get("title")), String(data.get("url"))); form.reset();
    });
  };
  private saveUpload = (event: SubmitEvent, cardId: string): void => {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement, data = new FormData(form);
    const file = data.get("file");
    if (!(file instanceof File) || !file.name) return;
    this.perform("File attached", async () => {
      await addUpload(cardId, String(data.get("title")), file); form.reset();
    });
  };
  private editComment = (item: Comment): void => {
    const body = window.prompt("Comment", item.body);
    if (body && body !== item.body) this.perform("Comment updated", () => editComment(item.id, body));
  };
  private editAttachment = (item: Attachment): void => {
    const title = window.prompt("Attachment title", item.title);
    if (!title) return;
    const url = item.kind === "link" ? window.prompt("Web address", item.url ?? "") : undefined;
    if (item.kind === "link" && !url) return;
    this.perform("Attachment updated", () => editAttachment(item.id, title, url ?? undefined));
  };

  private boardEditor() {
    const board = this.state.view?.board;
    if (!board || !this.state.editingBoard) return null;
    return <div class="backdrop"><section class="dialog" role="dialog" aria-modal="true"
      aria-labelledby="board-editor-title"><h2 id="board-editor-title">EDIT BOARD</h2>
      <form onSubmit={this.saveBoard}><label>Name<input name="name" required maxLength={120}
        value={board.name} /></label><label>Description<textarea name="description" maxLength={4000}
          value={board.description} /></label><div class="actions"><CommandButton type="button"
            onClick={() => this.setState({ editingBoard: false })}>CANCEL</CommandButton>
          <CommandButton type="submit">SAVE</CommandButton></div></form></section></div>;
  }
  private cardEditor() {
    const card = this.card(this.state.selected);
    if (!card && !this.state.creatingIn) return null;
    const value = card ?? { title: "", description: "", assignee: "", labels: [], priority: "normal" };
    const comments = active(this.state.view?.comments ?? []).filter((item) => item.card_id === card?.id);
    const attachments = active(this.state.view?.attachments ?? []).filter((item) => item.card_id === card?.id);
    return <div class="backdrop"><section class="dialog card-dialog" role="dialog" aria-modal="true"
      aria-labelledby="card-editor-title"><h2 id="card-editor-title">{card ? "CARD DETAILS" : "NEW CARD"}</h2>
      <form class="card-fields" onSubmit={this.saveCard}><label>Title<input name="title" required maxLength={120}
        value={value.title} /></label><label>Description<textarea name="description" maxLength={4000}
          value={value.description} /></label><div class="field-row"><label>Assignee<input name="assignee"
            maxLength={120} value={value.assignee} /></label><label>Priority<select name="priority"
              value={value.priority}><option value="low">Low</option><option value="normal">Normal</option>
              <option value="high">High</option><option value="urgent">Urgent</option></select></label></div>
        <label>Labels <span class="hint">comma separated</span><input name="labels"
          value={value.labels.join(", ")} /></label><div class="actions">{card && <CommandButton type="button"
            class="danger" onClick={() => this.archive("card", card.id, card.title)}>ARCHIVE</CommandButton>}
          <CommandButton type="button" onClick={() => this.setState({ selected: null, creatingIn: null })}>
            CLOSE</CommandButton><CommandButton type="submit">SAVE</CommandButton></div></form>
      {card && <div class="card-extras"><section><h3>COMMENTS</h3>{comments.map((item) => <div class="row">
        <p>{item.body}</p><CommandButton appearance="subtle" onClick={() => this.editComment(item)}>EDIT</CommandButton>
        <CommandButton appearance="subtle" onClick={() => this.archive("comment", item.id, "comment")}>
          ARCHIVE</CommandButton>
      </div>)}<form class="compact-form" onSubmit={(event) => this.saveComment(event, card.id)}>
        <input name="body" required maxLength={4000} placeholder="Write a comment" aria-label="Comment" />
        <CommandButton type="submit">ADD</CommandButton></form></section><section><h3>ATTACHMENTS</h3>
      {attachments.map((item) => <div class="row"><a href={item.kind === "link" ? item.url! :
        `/api/attachments/${item.id}/content`}>{item.title}</a><span>{item.kind.toUpperCase()}</span>
        <CommandButton appearance="subtle" onClick={() => this.editAttachment(item)}>EDIT</CommandButton>
        <CommandButton appearance="subtle" onClick={() => this.archive("attachment", item.id, item.title)}>
          ARCHIVE</CommandButton></div>)}<form class="compact-form" onSubmit={(event) => this.saveLink(event, card.id)}>
        <input name="title" required placeholder="Link title" aria-label="Link title" /><input name="url"
          type="url" required placeholder="https://…" aria-label="Web address" /><CommandButton type="submit">
          ADD LINK</CommandButton></form><form class="compact-form"
            onSubmit={(event) => this.saveUpload(event, card.id)}>
        <input name="title" required placeholder="File title" aria-label="File title" /><input name="file"
          type="file" required aria-label="Choose file" /><CommandButton type="submit">UPLOAD</CommandButton>
      </form></section></div>}</section></div>;
  }
  private column(column: NonNullable<State["view"]>["columns"][number]) {
    const cards = this.cards(column.id);
    return <ConsolePane class="column" title={column.name} tone="neutral" titleEnd={<>
      <CommandButton appearance="subtle" aria-label={`Rename ${column.name}`}
        onClick={() => this.renameColumn(column.id, column.name)}>EDIT</CommandButton>
      <CommandButton appearance="subtle" aria-label={`Archive ${column.name}`}
        onClick={() => this.archive("column", column.id, column.name)}>ARCHIVE</CommandButton></>}>
      <div class="card-list" data-column={column.id} onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => this.drop(event, column.id)}>{cards.map((card) => <article data-card-id={card.id}
          class={`card priority-${card.priority}`}
          draggable onDragStart={() => { this.dragged = card.id; }} onDragEnd={() => { this.dragged = null; }}
          onClick={() => this.setState({ selected: card.id })} onKeyDown={(event) => {
            if (event.key === "Enter") this.setState({ selected: card.id });
          }} tabIndex={0}><strong>{card.title}</strong>{card.description && <p>{card.description}</p>}
          <div class="card-meta">{card.labels.map((label) => <span>{label}</span>)}
            {card.assignee && <span>@{card.assignee}</span>}<span>{card.priority}</span></div></article>)}
        <CommandButton class="add-card" onClick={() => this.setState({ creatingIn: column.id })}>+ CARD</CommandButton>
      </div></ConsolePane>;
  }
  private board() {
    const columns = active(this.state.view?.columns ?? []).sort((a, b) => a.position - b.position);
    if (!columns.length) return <EmptyState heading="NO COLUMNS" detail="Create a column to begin your workflow." />;
    return <div class="board">{columns.map((column) => this.column(column))}</div>;
  }
  private archiveView() {
    const view = this.state.view!;
    const items = [
      ...view.columns.filter((item) => item.archived_at).map((item) => ["column", item.id, item.name]),
      ...view.cards.filter((item) => item.archived_at).map((item) => ["card", item.id, item.title]),
      ...view.comments.filter((item) => item.archived_at).map((item) => ["comment", item.id, item.body]),
      ...view.attachments.filter((item) => item.archived_at).map((item) => ["attachment", item.id, item.title]),
    ];
    return <ConsolePane title="ARCHIVE" tone="orange"><div class="archive-list">{items.length ? items.map((item) =>
      <div class="archive-row"><span>{item[0]}</span><strong>{item[2]}</strong><CommandButton
        onClick={() => this.perform(`${item[0]} restored`, () => setArchived(item[0]!, item[1]!, true))}>
          RESTORE</CommandButton></div>) : <EmptyState heading="ARCHIVE EMPTY" />}</div></ConsolePane>;
  }
  private activityView() {
    return <ConsolePane title="ACTIVITY" tone="purple"><ol class="activity-list">
      {this.state.view!.activity.map((item) => <li><time>{new Date(item.occurred_at).toLocaleString()}</time>
        <span>{item.summary}</span></li>)}</ol></ConsolePane>;
  }
  override render() {
    const view = this.state.view, board = view?.board;
    const header = <UtilityRail><strong class="brand">{board?.name ?? "KANBAN"}</strong>
      {board?.description && <span class="board-description">{board.description}</span>}<span class="push" />
      <CommandButton pressed={this.state.mode === "board"}
        onClick={() => this.setState({ mode: "board" })}>BOARD</CommandButton>
      <CommandButton pressed={this.state.mode === "activity"}
        onClick={() => this.setState({ mode: "activity" })}>ACTIVITY</CommandButton>
      <CommandButton pressed={this.state.mode === "archive"}
        onClick={() => this.setState({ mode: "archive" })}>ARCHIVE</CommandButton>
      <CommandButton onClick={() => this.setState({ editingBoard: true })}>EDIT BOARD</CommandButton>
      <CommandButton onClick={this.createColumn}>+ COLUMN</CommandButton></UtilityRail>;
    const footer = <StatusRail><span class={this.state.failed ? "error" : ""} role="status">
      {this.state.busy ? "SAVING…" : this.state.message}</span><span class="push">
      {active(view?.columns ?? []).length} COLUMNS · {active(view?.cards ?? []).length} CARDS</span></StatusRail>;
    return <ConsoleShell class="kanban-shell" header={header} footer={footer}><div class="workspace">
      {!view ? <EmptyState heading="LOADING BOARD" /> : this.state.mode === "board" ? this.board() :
        this.state.mode === "archive" ? this.archiveView() : this.activityView()}</div>
      {this.boardEditor()}{this.cardEditor()}</ConsoleShell>;
  }
}

export function mount(root: HTMLElement): void { render(<KanbanBoard />, root); }
