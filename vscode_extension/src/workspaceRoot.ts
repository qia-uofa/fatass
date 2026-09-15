import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

/** Finds the fatass project root: a workspace folder containing fatass/topology. */
export function findFatassRoot(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders) {
    return undefined;
  }
  for (const folder of folders) {
    const candidate = folder.uri.fsPath;
    if (fs.existsSync(path.join(candidate, "fatass", "topology"))) {
      return candidate;
    }
  }
  return undefined;
}

export function topologyDir(root: string): string {
  return path.join(root, "fatass", "topology");
}

export function homeDir(root: string): string {
  return path.join(root, "home");
}

// Mirrors `fatass.resolve.cwd.ROOT`/`PAREN_ROOT` -- the ONE place in this
// extension that knows the sentinel's actual spelling.
export const ROOT = "@";
export const PAREN_ROOT = `(${ROOT})`;

/** "writing_sample" -> "WritingSample" -- mirrors fatass's own
 * `_internal.naming.pascal_case`. Used only for display labels that have
 * no server round-trip already fetching a real node (`nodeLabel`'s
 * current-node title, `relativeDotPath`'s dependency label) -- anywhere
 * a `NodeItem` already exists, its own `pascalPath`/`absolutePath` (see
 * topologyProvider.ts) is server-computed via `fatass._internal.naming`
 * itself and should be used instead of calling this. */
function pascalCase(snake: string): string {
  return snake
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join("");
}

/** "my_node.other_thing[0]" -> "MyNode.OtherThing[0]" -- per-segment
 * PascalCase conversion (see `pascalCase`), preserving any "[idx]"
 * chain-index suffix on a segment as-is. */
export function toPascalPath(dotPath: string): string {
  return dotPath
    .split(".")
    .map((seg) => {
      const bracketIdx = seg.indexOf("[");
      const name = bracketIdx === -1 ? seg : seg.slice(0, bracketIdx);
      const suffix = bracketIdx === -1 ? "" : seg.slice(bracketIdx);
      return pascalCase(name) + suffix;
    })
    .join(".");
}

/** Path (relative to `.fatass/.env`) of the FATASS_NODE dotenv file. */
export function envPath(root: string): string {
  return path.join(root, ".fatass", ".env");
}

/**
 * Reads the current node (`FATASS_NODE`) from `.fatass/.env`, the same
 * plain KEY=VALUE dotenv format `fatass.resolve.dotenv` writes: "" (the
 * true topology root) if the file or variable is missing.
 */
export function readCurrentNode(root: string): string {
  const file = envPath(root);
  if (!fs.existsSync(file)) {
    return "";
  }
  const text = fs.readFileSync(file, "utf-8");
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) {
      continue;
    }
    const [key, ...rest] = line.split("=");
    if (key.trim() !== "FATASS_NODE") {
      continue;
    }
    let value = rest.join("=").trim();
    if (value.length >= 2 && value[0] === value[value.length - 1] && (value[0] === '"' || value[0] === "'")) {
      value = value.slice(1, -1);
    }
    return value === ROOT ? "" : value;
  }
  return "";
}
