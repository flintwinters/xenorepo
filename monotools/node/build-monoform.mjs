import { build } from "esbuild";
import { dirname, resolve } from "node:path";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

async function buildMonoForm(manifestPath, operationsPath, scriptOutput, styleOutput) {
  const manifest = JSON.parse(await readFile(resolve(root, manifestPath), "utf8"));
  const allowlist = JSON.parse(await readFile(resolve(root, operationsPath), "utf8"));
  const selected = { ...manifest, operations: allowlist.map((operationId) => {
    const operation = manifest.operations.find((candidate) => candidate.operationId === operationId);
    if (!operation) throw new Error(`MonoForm artifact references undeclared operation ${operationId}`);
    return operation;
  }) };
  const entry = resolve(root, "monotools/frontend/monoform-page.tsx");
  const result = await build({
    stdin: { contents: `import { mount } from ${JSON.stringify(entry)}; mount(document.getElementById("app"));`,
      resolveDir: root, sourcefile: "monoform-bootstrap.tsx", loader: "tsx" },
    bundle: true, format: "iife", platform: "browser", target: ["es2022"], jsx: "automatic",
    jsxImportSource: "preact", minify: true, legalComments: "none", write: false, outdir: "out",
    define: { MONOFORM_MANIFEST: JSON.stringify(selected) },
  });
  const script = result.outputFiles.find((output) => output.path.endsWith(".js"));
  const style = result.outputFiles.find((output) => output.path.endsWith(".css"));
  if (!script) throw new Error("MonoForm bundle produced no JavaScript output");
  await mkdir(dirname(resolve(root, scriptOutput)), { recursive: true });
  await writeFile(resolve(root, scriptOutput), script.contents);
  await writeFile(resolve(root, styleOutput), style?.contents ?? new Uint8Array());
}

const [, , manifest, operations, script, style] = process.argv;
if (!manifest || !operations || !script || !style) {
  process.stderr.write("Usage: node build-monoform.mjs MANIFEST OPERATIONS OUTPUT.js OUTPUT.css\n");
  process.exitCode = 2;
} else {
  buildMonoForm(manifest, operations, script, style).catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
