#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

const PROOFS = new Set(["acceptance", "browser-integration", "visual", "accessibility"]);

function fail(code, detail) {
  process.stderr.write(`${code}: ${detail}\n`);
  process.exitCode = 1;
}

function textOf(node, source) {
  return node && (ts.isStringLiteralLike(node) || ts.isNoSubstitutionTemplateLiteral(node))
    ? node.text : node?.getText(source);
}

function validate(filename) {
  let contents;
  try { contents = fs.readFileSync(filename, "utf8"); }
  catch (error) { return fail("BROWSER_SUITE_MISSING", error.message); }
  const kind = filename.endsWith(".ts") ? ts.ScriptKind.TS : ts.ScriptKind.JS;
  const source = ts.createSourceFile(filename, contents, ts.ScriptTarget.Latest, true, kind);
  const counts = Object.fromEntries([...PROOFS].map(proof => [proof, 0]));
  let tests = 0;
  function visit(node) {
    if (ts.isCallExpression(node)) {
      const expression = node.expression;
      const directTest = ts.isIdentifier(expression) && expression.text === "test";
      const testOnly = ts.isPropertyAccessExpression(expression)
        && ts.isIdentifier(expression.expression) && expression.expression.text === "test"
        && expression.name.text === "only";
      if (testOnly) fail("BROWSER_FORBID_ONLY", `${path.basename(filename)}:${source.getLineAndCharacterOfPosition(node.pos).line + 1}`);
      if (directTest || testOnly) {
        tests += 1;
        const title = textOf(node.arguments[0], source) || "";
        const tags = [...PROOFS].filter(proof => title.includes(`[${proof}]`));
        if (tags.length !== 1) fail("BROWSER_PROOF_TAG_COUNT", `${title || "unnamed test"} has ${tags.length} proof tags`);
        else {
          counts[tags[0]] += 1;
          const body = node.arguments[1]?.getText(source) || "";
          if (tags[0] !== "browser-integration" && /\.dispatchEvent\s*\(|new\s+(PointerEvent|MouseEvent|TouchEvent|KeyboardEvent)\s*\(/.test(body)) {
            fail("BROWSER_UNTRUSTED_ACCEPTANCE", title);
          }
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  if (source.parseDiagnostics.length) fail("BROWSER_PARSE_ERROR", source.parseDiagnostics[0].messageText);
  if (!tests) fail("BROWSER_NO_TESTS", filename);
  if (!process.exitCode) process.stdout.write(JSON.stringify({ schemaVersion: 1, tests, counts }) + "\n");
}

if (process.argv.length !== 3) fail("BROWSER_USAGE", "validate.js SUITE");
else validate(path.resolve(process.argv[2]));
