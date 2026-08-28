import { render } from "lit";
import { styles1 } from "./styles.js";
import { view } from "./view.js";

function start() {
  (() => {
    "use strict";
    const items = [
        { dimension: "FOCUS", text: "I can sustain attention on a demanding task without frequent switching." },
        { dimension: "STRUCTURE", text: "I prefer to make a clear plan before beginning unfamiliar work." },
        { dimension: "CONNECTION", text: "I gain energy from working through ideas with other people." },
        { dimension: "ADAPTABILITY", text: "I remain effective when a plan changes at short notice." },
        { dimension: "FOCUS", text: "I am comfortable setting aside distractions to complete a priority." },
        { dimension: "STRUCTURE", text: "I keep my work organized so that others can easily follow it." },
        { dimension: "CONNECTION", text: "I actively seek perspectives that differ from my own." },
        { dimension: "ADAPTABILITY", text: "I enjoy learning a new approach when the current one is not working." },
      ],
      labels = ["Strongly disagree", "Disagree", "Neither", "Agree", "Strongly agree"],
      $ = (id) => document.getElementById(id);
    let index = 0,
      responses = [];
    function profile() {
      return Object.fromEntries(
        ["FOCUS", "STRUCTURE", "CONNECTION", "ADAPTABILITY"].map((name) => {
          const values = responses
            .filter((response) => items[response.index].dimension === name)
            .map((response) => response.value);
          return [
            name,
            values.length ? Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 20) : null,
          ];
        }),
      );
    }
    function draw() {
      const complete = index === items.length,
        signals = profile();
      $("itemList").replaceChildren(
        ...items.map((item, i) => {
          const li = document.createElement("li");
          li.className = i === index && !complete ? "active" : "";
          li.innerHTML = `<span class="number">${String(i + 1).padStart(2, "0")}</span>
            <span>${responses[i] ? "RECORDED" : "PENDING"}</span>`;
          return li;
        }),
      );
      for (const name of Object.keys(signals))
        $(name.toLowerCase()).textContent =
          signals[name] === null ? "—" : `${signals[name]}%`;
      $("meter").style.width = `${(responses.length / items.length) * 100}%`;
      $("completion").textContent = `${responses.length} RECORDED`;
      $("review").replaceChildren(
        ...(responses.length
          ? responses.map((response, i) => {
              const li = document.createElement("li");
              li.innerHTML = `<span class="number">${String(i + 1).padStart(2, "0")}</span>
                <span>${items[i].text}</span><span class="result">
                ${labels[response.value - 1].toUpperCase()}</span>`;
              return li;
            })
          : [
              Object.assign(document.createElement("li"), {
                innerHTML:
                  '<span class="muted">—</span><span class="muted">' +
                  'Your responses will appear here.</span><span class="result">WAITING</span>',
              }),
            ]),
      );
      if (complete) {
        const strongest = Object.entries(signals).sort(([, a], [, b]) => b - a)[0][0];
        $("position").textContent = "PROFILE COMPLETE";
        $("dimension").textContent = strongest;
        $("prompt").textContent = `Your strongest current signal is ${strongest.toLowerCase()}.`;
        $("answers").innerHTML = '<button id="restartProfile">START AGAIN</button>';
        $("restartProfile").onclick = restart;
        $("message").innerHTML = "<strong>Profile recorded.</strong>" +
          "This brief inventory supports reflection, not diagnosis or selection decisions.";
        $("live").textContent = "COMPLETE";
        return;
      }
      const item = items[index],
        response = responses[index];
      $("position").textContent = `ITEM ${index + 1} / ${items.length}`;
      $("dimension").textContent = item.dimension;
      $("prompt").textContent = item.text;
      $("answers").replaceChildren(
        ...labels.map((label, i) => {
          const button = document.createElement("button");
          button.className = `answer ${response?.value === i + 1 ? "selected" : ""}`;
          button.innerHTML = `<span class="keynum">${i + 1}</span>${label}`;
          button.onclick = () => record(i + 1);
          return button;
        }),
      );
      $("live").textContent = "READY";
    }
    function record(value) {
      responses[index] = { index, value };
      $("message").innerHTML =
        "<strong>Response recorded.</strong>Press Enter to continue, or choose another response.";
      draw();
    }
    function next() {
      if (responses[index]) {
        index++;
        draw();
      }
    }
    function restart() {
      index = 0;
      responses = [];
      $("message").innerHTML = "<strong>There are no right answers.</strong>Choose the response that fits you best.";
      draw();
    }
    $("restart").onclick = restart;
    addEventListener("keydown", (event) => {
      if (event.key >= "1" && event.key <= "5" && index < items.length) {
        record(Number(event.key));
        event.preventDefault();
      } else if (event.key === "Enter") {
        next();
        event.preventDefault();
      } else if (event.key.toLowerCase() === "r") {
        restart();
        event.preventDefault();
      }
    });
    draw();
  })();
}

export function mount(root) {
  if (!root) throw new Error("missing application mount");
  document.title = "Working Style Inventory";
  for (const content of [styles1]) {
    const style = document.createElement("style");
    style.textContent = content;
    document.head.append(style);
  }
  render(view, root);
  start();
}
