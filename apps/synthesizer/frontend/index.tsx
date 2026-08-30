import { render } from "preact";
import { ConsolePane, ConsoleShell, StatusRail, UtilityRail } from "@xenorepo/ui";
import "./styles.css";

function Application() {
  const header = <UtilityRail><strong>Waveform Synthesizer</strong><span>WALKING SKELETON</span></UtilityRail>;
  const footer = <StatusRail><span>READY</span><span>MONOTOOLS MANAGED</span></StatusRail>;
  return <ConsoleShell class="app-shell" header={header} footer={footer}>
    <main class="workspace">
      <ConsolePane title="STATUS" tone="green">
        <p role="status">Waveform Synthesizer is ready for product behavior.</p>
      </ConsolePane>
    </main>
  </ConsoleShell>;
}

export function mount(root: HTMLElement): void { render(<Application />, root); }
