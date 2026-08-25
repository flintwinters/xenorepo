import ts from "typescript";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const configPath = resolve(root, "tsconfig.frontend.json");

function compilerOptions() {
  const loaded = ts.readConfigFile(configPath, ts.sys.readFile);
  if (loaded.error) throw new Error(ts.formatDiagnostic(loaded.error, formatHost));
  const parsed = ts.parseJsonConfigFileContent(loaded.config, ts.sys, root, undefined, configPath);
  if (parsed.errors.length) throw new Error(ts.formatDiagnostics(parsed.errors, formatHost));
  return parsed.options;
}

const formatHost = {
  getCanonicalFileName: (name) => name,
  getCurrentDirectory: () => root,
  getNewLine: () => "\n",
};

export function checkPageEntries(entries) {
  const roots = [resolve(root, "types/css.d.ts"), ...entries.map((entry) => resolve(root, entry))];
  const program = ts.createProgram(roots, compilerOptions());
  const diagnostics = ts.getPreEmitDiagnostics(program);
  if (!diagnostics.length) return;
  throw new Error(ts.formatDiagnosticsWithColorAndContext(diagnostics, formatHost).trimEnd());
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const entries = process.argv.slice(2);
  if (!entries.length) {
    process.stderr.write("Usage: node scripts/check-lit.mjs <entry.ts> [...]\n");
    process.exitCode = 2;
  } else {
    try {
      checkPageEntries(entries);
    } catch (error) {
      process.stderr.write(`${error.message}\n`);
      process.exitCode = 1;
    }
  }
}
