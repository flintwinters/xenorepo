import fs from "node:fs";
import path from "node:path";
import postcss from "postcss";
import ts from "typescript";

const forbiddenGlobal = new Set([
  "button", "input", "select", "textarea", "label", "form",
  "h1", "h2", "h3", "h4", "h5", "h6",
]);

function filesBelow(root, suffixes) {
  if (!fs.existsSync(root)) return [];
  return fs.readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const item = path.join(root, entry.name);
    return entry.isDirectory() ? filesBelow(item, suffixes)
      : suffixes.has(path.extname(entry.name)) ? [item] : [];
  }).sort();
}

function location(source, node, workspace) {
  const point = source.getLineAndCharacterOfPosition(node.getStart(source));
  return `${path.relative(workspace, source.fileName)}:${point.line + 1}:${point.character + 1}`;
}

function inspectTypescript(file, workspace, metrics, violations) {
  const text = fs.readFileSync(file, "utf8");
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  function visit(node) {
    if (ts.isImportDeclaration(node) && node.moduleSpecifier.text === "@xenorepo/ui") {
      metrics.toolkitImports += 1;
    }
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = node.tagName.getText(source);
      if (tag === "CommandButton") metrics.commandButtons += 1;
      if (tag === "EmptyState") metrics.emptyStates += 1;
      if (tag === "button") {
        const domain = node.attributes.properties.some((attribute) =>
          ts.isJsxAttribute(attribute) && attribute.name.getText(source) === "data-ui-control"
          && attribute.initializer?.getText(source).replaceAll(/["']/g, "") === "domain");
        if (domain) metrics.domainControls += 1;
        else violations.push({ code: "UNCLASSIFIED_NATIVE_BUTTON", location: location(source, node, workspace),
          detail: "use CommandButton, or mark a true direct-manipulation surface data-ui-control=\"domain\"" });
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
}

function bareGlobal(selector) {
  return selector.split(",").map((part) => part.trim()).filter((part) => {
    const match = part.match(/^([a-z][a-z0-9-]*)\b/i);
    return match && forbiddenGlobal.has(match[1].toLowerCase());
  });
}

function inspectCss(file, workspace, metrics, violations) {
  const root = postcss.parse(fs.readFileSync(file, "utf8"), { from: file });
  root.walkRules((rule) => {
    for (const selector of bareGlobal(rule.selector)) {
      metrics.globalSelectors.push(selector);
      violations.push({ code: "BARE_GLOBAL_SELECTOR",
        location: `${path.relative(workspace, file)}:${rule.source.start.line}:${rule.source.start.column}`,
        detail: `scope '${selector}' beneath an app-owned root class` });
    }
  });
  root.walkDecls((decl) => {
    if (/border(?:-|$)/.test(decl.prop) && decl.value !== "0" && decl.value !== "none") metrics.borders += 1;
    if (decl.prop === "gap" || decl.prop.endsWith("-gap")) metrics.gaps += 1;
    if (/^(?:margin|padding)(?:-|$)/.test(decl.prop)) metrics.spacingValues.push(decl.value);
    if (/(?:^|-)color$|^background(?:-color)?$/.test(decl.prop)) metrics.colors.push(decl.value);
    if (decl.prop === "border-radius") metrics.radii.push(decl.value);
    if (decl.prop === "box-shadow" || decl.prop === "text-shadow") metrics.shadows.push(decl.value);
    if (decl.prop.startsWith("--")) metrics.customProperties.push(decl.prop);
  });
}

export function analyzeUi(appDirectory, workspace = process.cwd()) {
  const frontend = path.join(appDirectory, "frontend");
  const metrics = { toolkitImports: 0, commandButtons: 0, emptyStates: 0, domainControls: 0,
    borders: 0, gaps: 0, spacingValues: [], colors: [], radii: [], shadows: [],
    customProperties: [], globalSelectors: [] };
  const violations = [];
  for (const file of filesBelow(frontend, new Set([".ts", ".tsx"])))
    inspectTypescript(file, workspace, metrics, violations);
  for (const file of filesBelow(frontend, new Set([".css"])))
    inspectCss(file, workspace, metrics, violations);
  for (const key of ["spacingValues", "colors", "radii", "shadows", "customProperties", "globalSelectors"])
    metrics[key] = [...new Set(metrics[key])].sort();
  return { schemaVersion: 1, app: path.basename(appDirectory), hardViolationCount: violations.length,
    violations, metrics };
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  if (process.argv.length !== 3) {
    process.stderr.write("Usage: node monotools/node/ui-hygiene.mjs APP_DIRECTORY\n");
    process.exitCode = 2;
  } else {
    const report = analyzeUi(path.resolve(process.argv[2]));
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
    if (report.hardViolationCount) process.exitCode = 1;
  }
}
