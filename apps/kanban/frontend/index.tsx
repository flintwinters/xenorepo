import { Component, render } from "preact";
import { CommandButton, ConsoleChrome, ConsolePane, ConsoleShell, EmptyState, Modal, MonoForm, StatusRail,
  UtilityRail, type MonoFormManifest } from "monoui";
import rawManifest from "../data/monoform.json";
import {
  addLink, addLog, addUpload, importBoard, loadBoard, moveCard, moveColumn, setArchived, setCardTags,
  type BoardImport,
  type Attachment, type Card, type Column, type KanbanView, type Tag,
} from "./client.js";
import { coloredSurfaceStyle } from "./color.js";
import "./styles.css";

type Mode = "boards" | "tags" | "archive" | "activity";
interface State {
  view: KanbanView | null;
  mode: Mode;
  selected: string | null;
  creatingIn: string | null;
  creatingColumn: boolean;
  importing: boolean;
  editingBoard: boolean;
  editingColumn: string | null;
  editingAttachment: string | null;
  message: string;
  failed: boolean;
  busy: boolean;
}

const active = <T extends { archived_at?: string | null }>(values: T[]): T[] =>
  values.filter((value) => !value.archived_at);
const currentState = (view: KanbanView) => {
  const columns = active(view.columns).map(({ id, name, color }) => ({ id, name, color }));
  const columnIds = new Set(columns.map((value) => value.id));
  const cards = active(view.cards).filter((value) => columnIds.has(value.column_id)).map(
    ({ id, column_id, title, tags }) => ({ id, column_id, title, tags }),
  );
  const cardIds = new Set(cards.map((value) => value.id));
  const { name, description, background_color, accent_color, tag_colors } = view.board;
  const tags = view.tags.filter((tag) => tag.kind === "tag").map((tag) => tag.name);
  return { name, description, background_color, accent_color, tag_colors, tags, columns, cards,
    logs: view.logs.filter((value) => cardIds.has(value.card_id)).map(
      ({ card_id, body, created_at }) => ({ card_id, body, created_at })),
    attachments: active(view.attachments).filter((value) => cardIds.has(value.card_id)).map(
      ({ card_id, kind, title, url, original_name, media_type }) =>
        ({ card_id, kind, title, url, original_name, media_type })),
  };
};
const monoform = rawManifest as MonoFormManifest;

class KanbanBoard extends Component<Record<string, never>, State> {
  override state: State = { view: null, mode: "boards", selected: null, creatingIn: null,
    creatingColumn: false, importing: false, editingBoard: false, editingColumn: null,
    editingAttachment: null, message: "Loading board…", failed: false, busy: false };
  private dragged: string | null = null;
  private draggedColumn: string | null = null;
  private draggedTag: string | null = null;
  private tagUpdates = new Map<string, Promise<void>>();

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
  private copyBoard = async (): Promise<void> => {
    if (!this.state.view) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(currentState(this.state.view), null, 2));
      this.setState({ message: "Board JSON copied", failed: false });
    } catch {
      this.setState({ message: "Could not copy board JSON", failed: true });
    }
  };
  private card(id: string | null): Card | null {
    return this.state.view?.cards.find((value) => value.id === id) ?? null;
  }
  private cards(columnId: string): Card[] {
    return active(this.state.view?.cards ?? []).filter((value) => value.column_id === columnId)
      .sort((a, b) => a.position - b.position);
  }
  private cardLogs(cardId: string) {
    return (this.state.view?.logs ?? []).filter((item) => item.card_id === cardId)
      .sort((left, right) => left.created_at.localeCompare(right.created_at));
  }
  private knownTags(): string[] {
    return (this.state.view?.tags ?? []).filter((tag) => tag.kind === "tag")
      .map((tag) => tag.name).sort((left, right) => left.localeCompare(right));
  }
  private setTagsImmediately(card: Card, tags: string[]): void {
    const view = this.state.view;
    if (!view) return;
    const unique = tags.filter((tag, index) =>
      tags.findIndex((candidate) => candidate.toLocaleLowerCase() === tag.toLocaleLowerCase()) === index);
    this.setState({ view: { ...view, cards: view.cards.map((item) =>
      item.id === card.id ? { ...item, tags: unique } : item) }, message: "Item tags updated", failed: false });
    const pending = (this.tagUpdates.get(card.id) ?? Promise.resolve()).catch(() => undefined)
      .then(() => setCardTags(card.id, unique));
    this.tagUpdates.set(card.id, pending);
    void pending.then(() => {
      if (this.tagUpdates.get(card.id) === pending) this.tagUpdates.delete(card.id);
    }).catch(async (error) => {
      if (this.tagUpdates.get(card.id) !== pending) return;
      this.tagUpdates.delete(card.id);
      try {
        const restored = await loadBoard();
        this.setState({ view: restored,
          message: error instanceof Error ? error.message : "Could not update item tags", failed: true });
      } catch (refreshError) {
        this.setState({ message: refreshError instanceof Error ? refreshError.message : "Could not update item tags",
          failed: true });
      }
    });
  }
  private assignDraggedTag(event: DragEvent, card: Card): void {
    event.preventDefault();
    const tag = this.draggedTag;
    this.draggedTag = null;
    if (tag) this.setTagsImmediately(card, [...card.tags, tag]);
  }
  private removeDraggedTag(event: DragEvent, card: Card): void {
    event.preventDefault();
    const tag = this.draggedTag;
    this.draggedTag = null;
    if (tag) this.setTagsImmediately(card,
      card.tags.filter((value) => value.toLocaleLowerCase() !== tag.toLocaleLowerCase()));
  }
  private archive = (kind: string, id: string): void => {
    if (kind === "card") this.setState({ selected: null });
    this.perform(`${kind} archived`, () => setArchived(kind, id));
  };
  private drop = (event: DragEvent, columnId: string): void => {
    event.preventDefault();
    if (!this.dragged) return;
    const id = this.dragged, position = this.cards(columnId).length;
    this.dragged = null;
    this.moveCardImmediately(id, columnId, position);
  };
  private moveCardImmediately = (id: string, columnId: string, requestedPosition: number): void => {
    const view = this.state.view, moving = view?.cards.find((card) => card.id === id);
    if (!view || !moving) return;
    const source = this.cards(moving.column_id).filter((card) => card.id !== id);
    const target = moving.column_id === columnId ? source : this.cards(columnId);
    const position = Math.min(Math.max(requestedPosition, 0), target.length);
    target.splice(position, 0, moving);
    const positions = new Map<string, { column_id: string; position: number }>();
    source.forEach((card, index) => positions.set(card.id, { column_id: moving.column_id, position: index }));
    target.forEach((card, index) => positions.set(card.id, { column_id: columnId, position: index }));
    this.setState({ view: { ...view, cards: view.cards.map((card) => {
      const moved = positions.get(card.id);
      return moved ? { ...card, ...moved } : card;
    }) }, message: "Card moved", failed: false });
    void moveCard(id, columnId, position).catch(async (error) => {
      try {
        const restored = await loadBoard();
        this.setState({ view: restored, message: error instanceof Error ? error.message : "Card move failed",
          failed: true });
      } catch (refreshError) {
        this.setState({ message: refreshError instanceof Error ? refreshError.message : "Card move failed",
          failed: true });
      }
    });
  };
  private dropColumn = (event: DragEvent, target: Column): void => {
    event.preventDefault();
    const identity = this.draggedColumn;
    if (!identity || identity === target.id) return;
    this.draggedColumn = null;
    const columns = active(this.state.view?.columns ?? []).sort((a, b) => a.position - b.position);
    this.perform("Column moved", () => moveColumn(identity,
      columns.findIndex((column) => column.id === target.id)));
  };
  private saveLog = (event: SubmitEvent, cardId: string): void => {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement, body = String(new FormData(form).get("body"));
    this.perform("Log entry added", async () => { await addLog(cardId, body); form.reset(); });
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
  private boardEditor() {
    const board = this.state.view?.board;
    if (!board || !this.state.editingBoard) return null;
    const knownTags = this.knownTags();
    return <Modal class="backdrop" contentClass="dialog" labelledBy="board-editor-title"
      onDismiss={() => this.setState({ editingBoard: false })}><h2 id="board-editor-title">BOARD SETTINGS</h2>
      <MonoForm manifest={monoform} operationId="edit_board_details" initialValues={board}
        onCancel={() => this.setState({ editingBoard: false })}
        onSuccess={() => { this.setState({ editingBoard: false }); void this.refresh("Board details updated"); }} />
      {knownTags.length > 0 && <fieldset><legend>Tag colors</legend>{knownTags.map((tag) =>
        <MonoForm manifest={monoform} operationId="set_tag_color" title={`Tag “${tag}”`}
          pathValues={{ tag }} initialValues={{
            color: board.tag_colors[tag.toLocaleLowerCase()] ?? board.accent_color,
          }} onSuccess={() => { this.setState({ editingBoard: false });
            void this.refresh(`Tag ${tag} color updated`); }} />)}</fieldset>}
    </Modal>;
  }
  private columnEditor() {
    const column: Column | undefined = this.state.view?.columns.find(
      (value) => value.id === this.state.editingColumn,
    );
    if (!column) return null;
    return <Modal class="backdrop" contentClass="dialog" labelledBy="column-editor-title"
      onDismiss={() => this.setState({ editingColumn: null })}><h2 id="column-editor-title">EDIT COLUMN</h2>
      <MonoForm manifest={monoform} operationId="edit_column" pathValues={{ column_id: column.id }}
        initialValues={column} onCancel={() => this.setState({ editingColumn: null })}
        onSuccess={() => { this.setState({ editingColumn: null }); void this.refresh("Column renamed"); }} />
      <div class="actions"><CommandButton type="button" class="danger" onClick={() => {
        this.setState({ editingColumn: null });
        this.archive("column", column.id);
      }}>ARCHIVE COLUMN</CommandButton></div>
    </Modal>;
  }
  private columnCreator() {
    if (!this.state.creatingColumn) return null;
    return <Modal class="backdrop" contentClass="dialog" labelledBy="column-creator-title"
      onDismiss={() => this.setState({ creatingColumn: false })}><h2 id="column-creator-title">NEW COLUMN</h2>
      <MonoForm manifest={monoform} operationId="create_column"
        onCancel={() => this.setState({ creatingColumn: false })}
        onSuccess={() => { this.setState({ creatingColumn: false }); void this.refresh("Column created"); }} />
    </Modal>;
  }
  private importDialog() {
    if (!this.state.importing) return null;
    const busy = this.state.busy;
    return <Modal class="backdrop" contentClass="dialog" labelledBy="import-title"
      onDismiss={() => { if (!busy) this.setState({ importing: false }); }}><h2 id="import-title">IMPORT JSON</h2>
      <form onSubmit={(event) => this.importJson(event)}><label>Import mode<select name="mode" disabled={busy}>
        <option value="append">Append to this board</option>
        <option value="replace">Replace all board content</option>
      </select></label><label>JSON file<input name="file" type="file" accept="application/json,.json"
        required disabled={busy} /></label><p>Replace removes current and archived work.
        Import is atomic and cannot be undone.</p>
      <div class="actions"><CommandButton type="submit" disabled={busy}>IMPORT</CommandButton>
        <CommandButton type="button" appearance="subtle" disabled={busy}
          onClick={() => this.setState({ importing: false })}>CANCEL</CommandButton></div></form></Modal>;
  }
  private importJson = async (event: SubmitEvent): Promise<void> => {
    event.preventDefault();
    const data = new FormData(event.currentTarget as HTMLFormElement);
    const file = data.get("file"), mode = data.get("mode") === "replace" ? "replace" : "append";
    if (!(file instanceof File)) return;
    this.setState({ busy: true });
    try {
      const document = JSON.parse(await file.text()) as BoardImport;
      await importBoard(mode, document);
      this.setState({ importing: false });
      await this.refresh(`${mode === "replace" ? "Replaced" : "Appended"} board JSON`);
    } catch (error) {
      this.setState({ message: error instanceof Error ? error.message : "Invalid import JSON",
        failed: true, busy: false });
    }
  };
  private attachmentEditor() {
    const attachment: Attachment | undefined = this.state.view?.attachments.find(
      (value) => value.id === this.state.editingAttachment,
    );
    if (!attachment) return null;
    return <Modal class="backdrop" contentClass="dialog" labelledBy="attachment-editor-title"
      onDismiss={() => this.setState({ editingAttachment: null })}>
      <h2 id="attachment-editor-title">EDIT ATTACHMENT</h2>
      <MonoForm manifest={monoform} operationId="edit_attachment"
        pathValues={{ attachment_id: attachment.id }} initialValues={attachment}
        onCancel={() => this.setState({ editingAttachment: null })}
        onSuccess={() => { this.setState({ editingAttachment: null });
          void this.refresh("Attachment updated"); }} />
    </Modal>;
  }
  private tagEditor(card: Card) {
    const assigned = new Set(card.tags.map((tag) => tag.toLocaleLowerCase()));
    const available = (this.state.view?.tags ?? []).filter((tag) =>
      tag.kind === "tag" && !assigned.has(tag.name.toLocaleLowerCase()));
    const start = (tag: string): void => { this.draggedTag = tag; };
    return <section class="tag-editor" aria-label="Item tags"><div class="tag-group"
      aria-label="Available tags" onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => this.removeDraggedTag(event, card)}><h3>AVAILABLE TAGS</h3><div class="tag-pool">
      {available.length ? available.map((tag: Tag) => <CommandButton type="button" appearance="subtle"
        draggable aria-label={`Assign ${tag.name}`} onDragStart={() => start(tag.name)}
        onDragEnd={() => { this.draggedTag = null; }}
        onClick={() => this.setTagsImmediately(card, [...card.tags, tag.name])}>{tag.name}</CommandButton>) :
        <span class="empty-tags">All tags assigned</span>}</div></div><div class="tag-group assigned-tags"
      aria-label="Assigned tags" onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => this.assignDraggedTag(event, card)}><h3>ITEM TAGS</h3><div class="tag-pool">
      {card.tags.length ? card.tags.map((tag) => <CommandButton type="button" appearance="subtle"
        draggable aria-label={`Remove ${tag}`} onDragStart={() => start(tag)}
        onDragEnd={() => { this.draggedTag = null; }}
        onClick={() => this.setTagsImmediately(card, card.tags.filter((value) => value !== tag))}>{tag}</CommandButton>) :
        <span class="empty-tags">Drop tags here</span>}</div></div></section>;
  }
  private cardEditor() {
    if (this.state.editingAttachment) return null;
    const card = this.card(this.state.selected);
    if (!card && !this.state.creatingIn) return null;
    const value = card ?? { title: "", tags: [] };
    const logs = card ? this.cardLogs(card.id) : [];
    const attachments = active(this.state.view?.attachments ?? []).filter((item) => item.card_id === card?.id);
    return <Modal class="backdrop" contentClass="dialog card-dialog" labelledBy="card-editor-title"
      onDismiss={() => this.setState({ selected: null, creatingIn: null })}>
      <h2 id="card-editor-title">{card ? "CARD DETAILS" : "NEW CARD"}</h2>
      <div class="card-fields"><MonoForm manifest={monoform}
        operationId={card ? "edit_card" : "create_card"}
        pathValues={card ? { card_id: card.id } : { column_id: this.state.creatingIn! }}
        initialValues={value} onCancel={() => this.setState({ selected: null, creatingIn: null })}
        onSuccess={() => {
          this.setState({ selected: null, creatingIn: null });
          void this.refresh(card ? "Card updated" : "Card created");
        }} />{card && this.tagEditor(card)}{card && <div class="actions"><CommandButton type="button" class="danger"
          onClick={() => this.archive("card", card.id)}>ARCHIVE</CommandButton></div>}</div>
      {card && <div class="card-extras"><section class="item-log"><h3>ITEM LOG</h3>{logs.length > 0 ? <ol>
        {logs.map((item) => <li><time dateTime={item.created_at}>
          {new Date(item.created_at).toLocaleString()}</time><span>{item.body}</span></li>)}</ol> :
        <p class="empty-log">No log entries.</p>}<form class="compact-form log-form"
          onSubmit={(event) => this.saveLog(event, card.id)}><input name="body" required maxLength={4000}
            placeholder="Record progress" aria-label="Log entry" /><CommandButton type="submit">
            ADD LOG</CommandButton></form></section><section><h3>ATTACHMENTS</h3>
      {attachments.map((item) => <div class="row"><a href={item.kind === "link" ? item.url! :
        `/api/attachments/${item.id}/content`}>{item.title}</a><span>{item.kind.toUpperCase()}</span>
        <CommandButton appearance="subtle"
          onClick={() => this.setState({ editingAttachment: item.id })}>EDIT</CommandButton>
        <CommandButton appearance="subtle" onClick={() => this.archive("attachment", item.id)}>
          ARCHIVE</CommandButton></div>)}<form class="compact-form" onSubmit={(event) => this.saveLink(event, card.id)}>
        <input name="title" required placeholder="Link title" aria-label="Link title" /><input name="url"
          type="url" required placeholder="https://…" aria-label="Web address" /><CommandButton type="submit">
          ADD LINK</CommandButton></form><form class="compact-form"
            onSubmit={(event) => this.saveUpload(event, card.id)}>
        <input name="title" required placeholder="File title" aria-label="File title" /><input name="file"
          type="file" required aria-label="Choose file" /><CommandButton type="submit">UPLOAD</CommandButton>
      </form></section></div>}</Modal>;
  }
  private cardItem(card: Card, draggable: boolean) {
    const latestLog = this.cardLogs(card.id).at(-1);
    return <article data-card-id={card.id} class="card"><ConsoleChrome appearance="subtle" class="card-chrome"
      draggable={draggable} onDragStart={draggable ? () => { this.dragged = card.id; } : undefined}
      onDragEnd={draggable ? () => { this.dragged = null; } : undefined} title={<strong>{card.title}</strong>}
      titleEnd={<><span class="card-badges">{card.tags.map((tag) => {
        const color = this.state.view?.board.tag_colors[tag.toLocaleLowerCase()] ?? "#1d2021";
        return <span style={coloredSurfaceStyle("--tag-color", "--tag-ink", color)}>{tag}</span>;
      })}</span><CommandButton appearance="link" class="card-edit" aria-label={`Edit ${card.title}`}
        onClick={() => this.setState({ selected: card.id })}>EDIT</CommandButton></>} />
      {latestLog && <div class="card-log"><time dateTime={latestLog.created_at}>
        {new Date(latestLog.created_at).toLocaleString()}</time><span>{latestLog.body}</span></div>}
    </article>;
  }
  private column(column: Column) {
    const cards = this.cards(column.id);
    return <ConsolePane class="column"
      style={coloredSurfaceStyle("--column-color", "--tone-ink", column.color)} title={column.name}
      tone="neutral" chromeProps={{ draggable: true, "aria-label": `Drag ${column.name} column`,
        onDragStart: () => { this.draggedColumn = column.id; },
        onDragEnd: () => { this.draggedColumn = null; },
        onDragOver: (event) => { if (this.draggedColumn) event.preventDefault(); },
        onDrop: (event) => this.dropColumn(event, column) }}
      titleEnd={<><CommandButton appearance="subtle"
        onClick={() => this.setState({ creatingIn: column.id })}>+ CARD</CommandButton>
      <CommandButton appearance="subtle" aria-label={`Rename ${column.name}`}
        onClick={() => this.setState({ editingColumn: column.id })}>EDIT</CommandButton></>}>
      <div class="card-list" data-column={column.id} onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => this.drop(event, column.id)}>{cards.map((card) => this.cardItem(card, true))}
      </div></ConsolePane>;
  }
  private boardsView() {
    const columns = active(this.state.view?.columns ?? []).sort((a, b) => a.position - b.position);
    if (!columns.length) return <EmptyState heading="NO COLUMNS" detail="Create a column to begin your workflow." />;
    return <div class="board">{columns.map((column) => this.column(column))}</div>;
  }
  private tagsView() {
    const cards = active(this.state.view?.cards ?? []);
    const count = (tag: Tag): number => tag.kind === "board" ? cards.length : cards.filter((card) =>
      card.tags.some((value) => value.toLocaleLowerCase() === tag.name.toLocaleLowerCase())).length;
    return <ConsolePane class="tag-catalog" title="TAGS" tone="neutral"><table>
      <thead><tr><th scope="col">NAME</th><th scope="col">TYPE</th><th scope="col">COLOR</th>
        <th scope="col">ASSIGNMENTS</th></tr></thead><tbody>{(this.state.view?.tags ?? []).map((tag) =>
        <tr data-tag={tag.name}><th scope="row">{tag.name}</th><td>{tag.kind === "board" ? "BOARD" : "TAG"}</td>
          <td><span class="tag-color" style={coloredSurfaceStyle("--tag-color", "--tag-ink", tag.color)}>
            {tag.color.toUpperCase()}</span></td><td>{count(tag)}</td></tr>)}</tbody>
    </table></ConsolePane>;
  }
  private archiveView() {
    const view = this.state.view!;
    const items = [
      ...view.columns.filter((item) => item.archived_at).map((item) => ["column", item.id, item.name]),
      ...view.cards.filter((item) => item.archived_at).map((item) => ["card", item.id, item.title]),
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
      <CommandButton disabled={!view} onClick={() => void this.copyBoard()}>COPY JSON</CommandButton>
      <CommandButton disabled={!view || this.state.busy}
        onClick={() => this.setState({ importing: true })}>IMPORT JSON</CommandButton>
      {board?.description && <span class="board-description">{board.description}</span>}<span class="push" />
      <CommandButton pressed={this.state.mode === "boards"}
        onClick={() => this.setState({ mode: "boards" })}>BOARDS</CommandButton>
      <CommandButton pressed={this.state.mode === "tags"}
        onClick={() => this.setState({ mode: "tags" })}>TAGS</CommandButton>
      <CommandButton pressed={this.state.mode === "activity"}
        onClick={() => this.setState({ mode: "activity" })}>ACTIVITY</CommandButton>
      <CommandButton pressed={this.state.mode === "archive"}
        onClick={() => this.setState({ mode: "archive" })}>ARCHIVE</CommandButton>
      <CommandButton onClick={() => this.setState({ editingBoard: true })}>EDIT BOARD</CommandButton>
      <CommandButton onClick={() => this.setState({ creatingColumn: true })}>+ COLUMN</CommandButton></UtilityRail>;
    const footer = <StatusRail><span class={this.state.failed ? "error" : ""} role="status">
      {this.state.busy ? "SAVING…" : this.state.message}</span><span class="push">
      {active(view?.columns ?? []).length} COLUMNS · {active(view?.cards ?? []).length} CARDS</span></StatusRail>;
    return <ConsoleShell class="kanban-shell" header={header} footer={footer}><div class="workspace">
      {!view ? <EmptyState heading="LOADING BOARD" /> : this.state.mode === "boards" ? this.boardsView() :
        this.state.mode === "tags" ? this.tagsView() : this.state.mode === "archive" ? this.archiveView() :
          this.activityView()}</div>
      {this.boardEditor()}{this.columnCreator()}{this.columnEditor()}
      {this.attachmentEditor()}{this.cardEditor()}{this.importDialog()}</ConsoleShell>;
  }
}

export function mount(root: HTMLElement): void { render(<KanbanBoard />, root); }
