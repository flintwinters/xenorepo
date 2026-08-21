import { build } from "esbuild";
import { dirname, resolve } from "node:path";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

/** Bundle one Lit mount entry into a browser-ready, self-contained script. */
export async function buildPageEntry(entry, output) {
  const destination = resolve(root, output);
  await mkdir(dirname(destination), { recursive: true });
  await build({
    stdin: {
      contents: `import { mount } from ${JSON.stringify(resolve(root, entry))};\nmount(document.getElementById("app"));`,
      resolveDir: root,
      sourcefile: "lit-page-bootstrap.ts",
      loader: "ts",
    },
    outfile: destination,
    bundle: true,
    format: "iife",
    platform: "browser",
    target: ["es2022"],
    loader: { ".css": "text" },
    minify: true,
    legalComments: "none",
  });
}

function usage() {
  process.stderr.write("Usage: npm run build:lit -- <entry.ts> <output.js>\\n");
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [, , entry, output] = process.argv;
  if (!entry || !output) {
    usage();
    process.exitCode = 2;
  } else {
    buildPageEntry(entry, output).catch((error) => {
      process.stderr.write(`${error.message}\\n`);
      process.exitCode = 1;
    });
  }
}
