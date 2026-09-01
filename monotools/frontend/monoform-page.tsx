import { render } from "preact";
import { ConsolePane, ConsoleShell, MonoForm } from "@xenorepo/ui";
import type { MonoFormManifest, MonoFormResult } from "@xenorepo/ui";

declare const MONOFORM_MANIFEST: MonoFormManifest;

function GeneratedForms() {
  const report = (result: MonoFormResult): void => {
    const node = document.getElementById("monoform-result");
    if (node) node.textContent = `${result.operationId} completed (${result.status}).`;
  };
  return <ConsoleShell header={<strong>{MONOFORM_MANIFEST.application.title}</strong>}>
    <div id="monoform-result" role="status" />
    {MONOFORM_MANIFEST.operations.map((operation) =>
      <ConsolePane title={operation.title} contentHeight>
        <MonoForm manifest={MONOFORM_MANIFEST} operationId={operation.operationId} onSuccess={report} />
      </ConsolePane>)}
  </ConsoleShell>;
}

export function mount(root: HTMLElement): void {
  render(<GeneratedForms />, root);
}
