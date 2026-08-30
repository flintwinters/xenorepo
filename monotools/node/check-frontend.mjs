import ts from "typescript";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const formatHost = {
  getCanonicalFileName: (name) => name,
  getCurrentDirectory: () => root,
  getNewLine: () => "\n",
};

function compilerOptions(configPath) {
  const loaded = ts.readConfigFile(configPath, ts.sys.readFile);
  if (loaded.error) throw new Error(ts.formatDiagnostic(loaded.error, formatHost));
  const parsed = ts.parseJsonConfigFileContent(loaded.config, ts.sys, root, undefined, configPath);
  if (parsed.errors.length) throw new Error(ts.formatDiagnostics(parsed.errors, formatHost));
  return parsed.options;
}

export function checkPageEntries(entries) {
  const configPath = resolve(root, "tsconfig.preact.json");
  const roots = [resolve(root, "types/css.d.ts"), ...entries.map((entry) => resolve(root, entry))];
  const diagnostics = ts.getPreEmitDiagnostics(ts.createProgram(roots, compilerOptions(configPath)));
  if (diagnostics.length)
    throw new Error(ts.formatDiagnosticsWithColorAndContext(diagnostics, formatHost).trimEnd());
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const entries = process.argv.slice(2);
  if (!entries.length) {
    process.stderr.write("Usage: node monotools/node/check-frontend.mjs ENTRY [... ]\n");
    process.exitCode = 2;
  } else {
    try { checkPageEntries(entries); }
    catch (error) {
      process.stderr.write(`${error.message}\n`);
      process.exitCode = 1;
    }
  }
}
