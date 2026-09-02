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

/** True if `dir` is itself a node directory: contains `<dirname>.py`. */
export function isNodeDir(dir: string): boolean {
  const name = path.basename(dir);
  return fs.existsSync(path.join(dir, `${name}.py`));
}
