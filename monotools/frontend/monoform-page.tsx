import { render } from "preact";
import { useState } from "preact/hooks";
import { ConsolePane, ConsoleShell, MonoForm } from "@xenorepo/ui";
import type { MonoFormManifest, MonoFormResult } from "@xenorepo/ui";

declare const MONOFORM_MANIFEST: MonoFormManifest;

function GeneratedForms() {
  const [outcome, setOutcome] = useState("");
  const report = (result: MonoFormResult): void => {
    const data = result.data === null ? "" : ` ${JSON.stringify(result.data)}`;
    setOutcome(`${result.operationId} completed (${result.status}).${data}`);
  };
  return <ConsoleShell header={<strong>{MONOFORM_MANIFEST.application.title}</strong>}>
    <div><div id="monoform-result" role="status">{outcome}</div>
      {MONOFORM_MANIFEST.operations.map((operation) =>
        <ConsolePane title={operation.title} contentHeight>
          <MonoForm manifest={MONOFORM_MANIFEST} operationId={operation.operationId} onSuccess={report} />
        </ConsolePane>)}
    </div>
  </ConsoleShell>;
}

export function mount(root: HTMLElement): void {
  render(<GeneratedForms />, root);
}
