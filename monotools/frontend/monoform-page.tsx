import { render } from "preact";
import { useState } from "preact/hooks";
import { ConsolePane, ConsoleShell, MonoForm, UtilityRail } from "monoui";
import type { MonoFormManifest, MonoFormResult } from "monoui";

declare const MONOFORM_MANIFEST: MonoFormManifest;

function GeneratedForms() {
  const [outcome, setOutcome] = useState("");
  const report = (result: MonoFormResult): void => {
    const data = result.data === null ? "" : ` ${JSON.stringify(result.data)}`;
    setOutcome(`${result.operationId} completed (${result.status}).${data}`);
  };
  const header = <UtilityRail><strong>{MONOFORM_MANIFEST.application.title}</strong></UtilityRail>;
  return <ConsoleShell class="x-ui-monoform-page" header={header}>
    <div class="x-ui-monoform-workspace">
      {MONOFORM_MANIFEST.operations.map((operation) =>
        <ConsolePane key={operation.operationId} title={operation.title} contentHeight>
          <div class="x-ui-monoform-result-surface">
            <strong>Result</strong>
            <div class="x-ui-monoform-result" role="status">{outcome}</div>
          </div>
          <MonoForm manifest={MONOFORM_MANIFEST} operationId={operation.operationId}
            showTitle={false} onSuccess={report} />
        </ConsolePane>)}
    </div>
  </ConsoleShell>;
}

export function mount(root: HTMLElement): void {
  render(<GeneratedForms />, root);
}
