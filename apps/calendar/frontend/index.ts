import {html, LitElement} from 'lit';
import {customElement} from 'lit/decorators.js';

@customElement('calendar-console')
class CalendarConsole extends LitElement {
  render() { return html`<main>Calendar Console</main>`; }
}

export function mount(): void {
  document.body.append(document.createElement('calendar-console'));
}
