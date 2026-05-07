#!/usr/bin/env node
// Regenerates static/types/page.d.ts from schema/page.schema.json.
// Run by `npm run build` (or `bun run build`) before bundling.

import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const schemaPath = resolve(ROOT, "schema/page.schema.json");
const outPath = resolve(ROOT, "static/types/page.d.ts");

const schema = JSON.parse(await readFile(schemaPath, "utf8"));

function pascal(name) {
  return name.charAt(0).toUpperCase() + name.slice(1);
}

function tsType(node) {
  if (!node) return "unknown";
  if (node.$ref) {
    const refName = node.$ref.split("/").pop();
    return pascal(refName);
  }
  if (node.enum) {
    return node.enum.map((v) => JSON.stringify(v)).join(" | ");
  }
  switch (node.type) {
    case "string":
      return "string";
    case "integer":
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    case "array":
      return `${tsType(node.items)}[]`;
    case "object":
      return objectShape(node);
    default:
      return "unknown";
  }
}

function objectShape(node) {
  const required = new Set(node.required || []);
  const props = node.properties || {};
  const lines = Object.entries(props).map(([key, value]) => {
    const optional = required.has(key) ? "" : "?";
    const doc = value.description ? `  /** ${value.description} */\n  ` : "  ";
    return `${doc}${key}${optional}: ${tsType(value)};`;
  });
  return `{\n${lines.join("\n")}\n}`;
}

let out = "// Generated from schema/page.schema.json by tools/gen-page-types.mjs.\n";
out += "// Do not edit by hand — your changes will be overwritten on the next build.\n\n";

for (const [name, def] of Object.entries(schema.$defs || {})) {
  out += `export interface ${pascal(name)} ${objectShape(def)}\n\n`;
}

out += `export interface ${pascal(schema.title.split(" ").pop())} ${objectShape(schema)}\n`;

await mkdir(dirname(outPath), { recursive: true });
await writeFile(outPath, out, "utf8");
console.log(`gen-page-types: wrote ${outPath}`);
