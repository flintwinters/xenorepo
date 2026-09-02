import { CommandButton, EmptyState } from "monoui";

export const View = () => <main class="fixture-root">
  <CommandButton>RESET</CommandButton>
  <button data-ui-control="domain">DIRECT OBJECT</button>
  <EmptyState heading="NO ITEMS" />
</main>;
