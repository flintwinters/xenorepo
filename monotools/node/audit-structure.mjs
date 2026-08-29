/** Measure JavaScript and TypeScript function complexity for Monotools audits. */
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const maximum = 8;
const results = [];

function sourceFor(filename) {
  const contents = fs.readFileSync(filename, "utf8");
  if (!filename.endsWith(".html")) return contents;
  return [...contents.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)]
    .map(match => match[1]).join("\n");
}

function functionName(node) {
  if (node.name?.getText) return node.name.getText();
  const parent = node.parent;
  if (ts.isVariableDeclaration(parent) && parent.name) return parent.name.getText();
  return "<anonymous>";
}

function complexityOf(root) {
  let complexity = 1;
  function visit(node) {
    if (node !== root && ts.isFunctionLike(node)) return;
    if (ts.isIfStatement(node) || ts.isForStatement(node) || ts.isForInStatement(node)
        || ts.isForOfStatement(node) || ts.isWhileStatement(node) || ts.isDoStatement(node)
        || ts.isCatchClause(node) || ts.isConditionalExpression(node) || ts.isCaseClause(node)) {
      complexity += 1;
    } else if (ts.isBinaryExpression(node)
        && [ts.SyntaxKind.AmpersandAmpersandToken, ts.SyntaxKind.BarBarToken,
          ts.SyntaxKind.QuestionQuestionToken].includes(node.operatorToken.kind)) {
      complexity += 1;
    }
    ts.forEachChild(node, visit);
  }
  ts.forEachChild(root, visit);
  return complexity;
}

for (const filename of process.argv.slice(2)) {
  const source = ts.createSourceFile(filename, sourceFor(filename), ts.ScriptTarget.Latest, true,
    filename.endsWith(".ts") || filename.endsWith(".tsx") ? ts.ScriptKind.TS : ts.ScriptKind.JS);
  function visit(node) {
    if (ts.isFunctionLike(node) && node.body) {
      const complexity = complexityOf(node);
      if (complexity > maximum) {
        const line = source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
        results.push({
          path: `${filename}:${line}`,
          detail: `${functionName(node)}: ${complexity} (maximum ${maximum})`,
        });
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
}

results.sort((left, right) => left.path.localeCompare(right.path) || left.detail.localeCompare(right.detail));
process.stdout.write(`${JSON.stringify(results)}\n`);
