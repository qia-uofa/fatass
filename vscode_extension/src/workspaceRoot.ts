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

const FATASS_ROOT_SENTINEL = "~";

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
    return value === FATASS_ROOT_SENTINEL ? "" : value;
  }
  return "";
}
