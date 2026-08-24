import { build } from "esbuild";
import { dirname, resolve } from "node:path";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const marker = "/* APP_BUNDLE */";

/** Bundle a dependency-free TypeScript entry into its adjacent HTML document. */
export async function buildDocumentEntry(entry, output) {
  const source = resolve(root, entry);
  const templatePath = resolve(dirname(source), "index.html");
  const template = await readFile(templatePath, "utf8");
  if (!template.includes(marker)) {
    throw new Error(`${templatePath} does not contain ${marker}`);
  }
  const result = await build({
    entryPoints: [source],
    bundle: true,
    format: "iife",
    platform: "browser",
    target: ["es2022"],
    minify: true,
    legalComments: "none",
    write: false,
  });
  const destination = resolve(root, output);
  await mkdir(dirname(destination), { recursive: true });
  await writeFile(destination, template.replace(marker, result.outputFiles[0].text));
}

function usage() {
  process.stderr.write("Usage: npm run build:typescript -- <entry.ts> <output.html>\n");
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [, , entry, output] = process.argv;
  if (!entry || !output) {
    usage();
    process.exitCode = 2;
  } else {
    buildDocumentEntry(entry, output).catch((error) => {
      process.stderr.write(`${error.message}\n`);
      process.exitCode = 1;
    });
  }
}
