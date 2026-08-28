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

function testCall(node) {
  if (!ts.isCallExpression(node)) return null;
  const expression = node.expression;
  const direct = ts.isIdentifier(expression) && expression.text === "test";
  const only = ts.isPropertyAccessExpression(expression)
    && ts.isIdentifier(expression.expression) && expression.expression.text === "test"
    && expression.name.text === "only";
  return direct || only ? { node, only } : null;
}

function validateTest(call, filename, source, counts) {
  const { node, only } = call;
  if (only) fail("BROWSER_FORBID_ONLY", `${path.basename(filename)}:${source.getLineAndCharacterOfPosition(node.pos).line + 1}`);
  const title = textOf(node.arguments[0], source) || "";
  const tags = [...PROOFS].filter(proof => title.includes(`[${proof}]`));
  if (tags.length !== 1) {
    fail("BROWSER_PROOF_TAG_COUNT", `${title || "unnamed test"} has ${tags.length} proof tags`);
    return;
  }
  counts[tags[0]] += 1;
  validateTrustedAcceptance(node, title, tags[0], source);
}

function validateTrustedAcceptance(node, title, proof, source) {
  const body = node.arguments[1]?.getText(source) || "";
  const synthetic = /\.dispatchEvent\s*\(|new\s+(PointerEvent|MouseEvent|TouchEvent|KeyboardEvent)\s*\(/;
  if (proof !== "browser-integration" && synthetic.test(body)) {
    fail("BROWSER_UNTRUSTED_ACCEPTANCE", title);
  }
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
    const call = testCall(node);
    if (call) {
      tests += 1;
      validateTest(call, filename, source, counts);
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
