import { render } from "preact";
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { CommandButton, ConsolePane, ConsoleShell, EmptyState, Modal, StatusRail,
  Table, UtilityRail, type TableColumn } from "monoui";
import { ContactForm } from "./contact-form.js";
import type { Contact } from "./client.js";
import "./styles.css";

interface ContactPage { items: Contact[]; page: number; page_size: number; total: number; pages: number }
type Sort = "name" | "email" | "company" | "job_title" | "city";

async function loadContacts(query: string, sort: Sort, direction: "asc" | "desc", page: number) {
  const params = new URLSearchParams({ q: query, sort, direction, page: String(page), page_size: "20" });
  const response = await fetch(`/api/contacts?${params}`);
  if (!response.ok) throw new Error(`Could not load contacts (${response.status})`);
  return await response.json() as ContactPage;
}

function Application() {
  const [view, setView] = useState<ContactPage | null>(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("name");
  const [direction, setDirection] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Contact | "new" | null>(null);
  const [message, setMessage] = useState("Loading contacts…");
  const [failed, setFailed] = useState(false);
  const requestNumber = useRef(0);
  const refresh = async () => {
    const request = ++requestNumber.current;
    try {
      const result = await loadContacts(query, sort, direction, page);
      if (request !== requestNumber.current) return;
      setView(result); setFailed(false); setMessage(`${result.total} contacts`);
    } catch (error) {
      if (request !== requestNumber.current) return;
      setFailed(true); setMessage(error instanceof Error ? error.message : "Could not load contacts");
    }
  };
  useEffect(() => { void refresh(); }, [query, sort, direction, page]);
  const sortBy = (next: Sort) => {
    setDirection(next === sort && direction === "asc" ? "desc" : "asc");
    setSort(next); setPage(1);
  };
  const heading = (label: string, field: Sort) => <CommandButton appearance="link" class="sort-heading"
    aria-label={`Sort by ${label}`} onClick={() => sortBy(field)}>
    <span>{label}</span><span aria-hidden="true">{sort === field ? (direction === "asc" ? "▲" : "▼") : "↕"}</span>
  </CommandButton>;
  const columns = useMemo<TableColumn<Contact>[]>(() => [
    { key: "name", header: heading("Name", "name"), width: "18%", rowHeader: true,
      sortDirection: sort === "name" ? `${direction}ending` : "none", render: (contact) => contact.name },
    { key: "email", header: heading("Email", "email"), width: "30%",
      sortDirection: sort === "email" ? `${direction}ending` : "none",
      render: (contact) => <a href={`mailto:${contact.email}`}>{contact.email}</a> },
    { key: "company", header: heading("Company", "company"), width: "25%", class: "mobile-hidden",
      sortDirection: sort === "company" ? `${direction}ending` : "none",
      render: (contact) => contact.company || "—" },
    { key: "role", header: heading("Role", "job_title"), width: "15%", class: "mobile-hidden",
      sortDirection: sort === "job_title" ? `${direction}ending` : "none",
      render: (contact) => contact.job_title || "—" },
    { key: "city", header: heading("City", "city"), width: "12%", class: "mobile-hidden",
      sortDirection: sort === "city" ? `${direction}ending` : "none",
      render: (contact) => contact.city || "—" },
    { key: "actions", header: <span class="visually-hidden">Actions</span>, width: "64px", class: "actions",
      render: (contact) => <CommandButton appearance="subtle"
        onClick={() => setEditing(contact)}>EDIT</CommandButton> },
  ], [sort, direction]);
  const changed = () => { setEditing(null); void refresh(); };
  const current = editing === "new" ? null : editing;
  return <ConsoleShell class="app-shell"
    header={<UtilityRail><strong>CONTACT BOOK</strong><span class="push">{view?.total ?? 0} PEOPLE</span>
      <CommandButton onClick={() => setEditing("new")}>+ CONTACT</CommandButton></UtilityRail>}
    footer={<StatusRail><span role="status" class={failed ? "error" : ""}>{message}</span>
      <span>PAGE {view?.page ?? page} / {view?.pages ?? 1}</span></StatusRail>}>
    <ConsolePane class="directory" title="DIRECTORY" tone="green">
      <div class="controls" aria-label="Directory controls">
      <label><span>SEARCH</span><input aria-label="Search contacts" value={query}
        onInput={(event) => { setQuery(event.currentTarget.value); setPage(1); }} /></label>
      </div>
      {view?.items.length ? <Table aria-label="Contacts" columns={columns} rows={view.items}
        rowKey={(contact) => contact.id} /> : <EmptyState heading={failed ? "DIRECTORY UNAVAILABLE" : "NO CONTACTS"}
        detail={failed ? "Change the query or retry when the service is available." : "Create or seed a contact."} />}
      <nav class="pager" aria-label="Contact pages"><CommandButton disabled={page <= 1}
        onClick={() => setPage(page - 1)}>PREVIOUS</CommandButton><span>PAGE {view?.page ?? page}</span>
        <CommandButton disabled={!view || page >= view.pages}
          onClick={() => setPage(page + 1)}>NEXT</CommandButton></nav>
    </ConsolePane>
    {editing && <Modal labelledBy="contact-editor-title" onDismiss={() => setEditing(null)}
      contentClass="dialog"><h2 id="contact-editor-title">{current ? "EDIT CONTACT" : "NEW CONTACT"}</h2>
      <ContactForm contact={current} onCancel={() => setEditing(null)} onChanged={changed} /></Modal>}
  </ConsoleShell>;
}

export function mount(root: HTMLElement): void { render(<Application />, root); }
