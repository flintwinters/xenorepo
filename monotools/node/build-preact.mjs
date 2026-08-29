import { build } from "esbuild";
import { dirname, resolve } from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

/** Bundle one Preact mount entry and its imported CSS into self-contained payloads. */
export async function buildPageEntry(entry, scriptOutput, styleOutput) {
  const result = await build({
    stdin: {
      contents: `import { mount } from ${JSON.stringify(resolve(root, entry))};\n`
        + `mount(document.getElementById("app"));`,
      resolveDir: root,
      sourcefile: "preact-page-bootstrap.tsx",
      loader: "tsx",
    },
    bundle: true,
    format: "iife",
    platform: "browser",
    target: ["es2022"],
    jsx: "automatic",
    jsxImportSource: "preact",
    minify: true,
    legalComments: "none",
    write: false,
    outdir: "out",
  });
  const script = result.outputFiles.find((output) => output.path.endsWith(".js"));
  const style = result.outputFiles.find((output) => output.path.endsWith(".css"));
  if (!script) throw new Error("Preact bundle produced no JavaScript output");
  await mkdir(dirname(resolve(root, scriptOutput)), { recursive: true });
  await writeFile(resolve(root, scriptOutput), script.contents);
  await writeFile(resolve(root, styleOutput), style?.contents ?? new Uint8Array());
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [, , entry, scriptOutput, styleOutput] = process.argv;
  if (!entry || !scriptOutput || !styleOutput) {
    process.stderr.write("Usage: npm run build:preact -- ENTRY.tsx OUTPUT.js OUTPUT.css\n");
    process.exitCode = 2;
  } else {
    buildPageEntry(entry, scriptOutput, styleOutput).catch((error) => {
      process.stderr.write(`${error.message}\n`);
      process.exitCode = 1;
    });
  }
}
