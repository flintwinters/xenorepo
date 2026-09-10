# Contact Book walking-skeleton specification

## Outcome

Contact Book proves a compact, durable contact directory and contributes a reusable, purely
presentational table to MonoUI. A person can browse generated contacts, refine and reorder the
visible result, move between pages, and create, edit, or delete a contact without leaving the
directory.

## Responsibilities and invariants

- Contact Book owns contact fields, CRUD, query semantics, page state, and the API contract.
- MonoUI's table owns accessible table structure and stable presentation classes only. Supplied
  columns and rows fully determine its view; it does not fetch, filter, sort, paginate, select, or
  mutate data.
- Contact identifiers are stable UUIDs. Normalized email addresses are unique. Names and email
  addresses are required; optional phone, company, job title, city, and tags remain app-owned facts.
- Mutations validate before changing durable state. Missing contacts and duplicate emails return
  contextual errors without affecting unrelated records.
- List responses have deterministic ordering with an identity tie-breaker and bounded page sizes.

## Walking skeleton

1. A deterministic management command populates the local database with 500 realistic contacts
   by default and can be repeated without duplicating its generated identities.
2. The directory requests one bounded page and renders it through the shared MonoUI table.
3. App-owned controls change the query, sort, direction, and page; the resulting server data alone
   changes the table view.
4. MonoForm-backed dialogs create, edit, and delete contacts, then refresh the current directory.
5. Empty, loading, validation, conflict, missing-record, and transport-failure states remain explicit
   and recoverable.

## Interaction contract

MonoForm is suitable for contact create, update, and delete because these are conventional scalar
CRUD operations. Search, ordering, and pagination are product-owned controls around the read-only
table. The table accepts typed column descriptions, typed rows, an app-supplied stable row key, and
cell renderers; it adds no hidden data transformations or interaction policy.

## Acceptance criteria

- Python tests prove persistence, validation, deterministic seeding, repeated seeding, CRUD, and
  bounded list/query/order/page behavior through public HTTP routes.
- Browser acceptance proves a populated directory can be searched, sorted, paged, created, edited,
  and deleted at wide and narrow viewports.
- MonoUI tests prove headers, cells, row identity, custom cell rendering, empty bodies, and arbitrary
  supplied row changes without implementing data operations.
- A second existing monoapp consumes the same table contract, and the library catalog records the
  proven shared responsibility.
- Root `uv run manage.py verify` passes; app-owned visual evidence is generated locally and remains
  unversioned.
