import { render } from "preact";
import { ConsolePane, ConsoleShell, StatusRail, UtilityRail } from "@xenorepo/ui";
import "./styles.css";

function Application() {
  const header = <UtilityRail><strong>Kanban</strong><span>WALKING SKELETON</span></UtilityRail>;
  const footer = <StatusRail><span>READY</span><span>MONOTOOLS MANAGED</span></StatusRail>;
  return <ConsoleShell class="app-shell" header={header} footer={footer}>
    <div class="workspace">
      <ConsolePane title="STATUS" tone="green">
        <p role="status" tabIndex={0}>Kanban is ready for product behavior.</p>
      </ConsolePane>
    </div>
  </ConsoleShell>;
}

export function mount(root: HTMLElement): void { render(<Application />, root); }
