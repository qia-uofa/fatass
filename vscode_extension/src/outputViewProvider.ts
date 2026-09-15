import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { FileItem } from "./nodeViewProvider";

/** Plain, read-only browser for `out/` (see `fatass._internal.paths.
 * OUT_ROOT`) -- the dispatch log and `fatass graph`'s own default `.puml`
 * output, and anywhere else a future command writes something meant for a
 * human to read rather than a node's own `home/` content. No "current
 * node" concept here (unlike the Node view) -- one fixed root, so no
 * synthetic "root" wrapper row is needed either. */
export class OutputViewProvider implements vscode.TreeDataProvider<FileItem> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<FileItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private readonly outDir: string;

  constructor(root: string) {
    this.outDir = path.join(root, "out");
  }

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: FileItem): vscode.TreeItem {
    return element;
  }

  private listDir(dir: string): FileItem[] {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return [];
    }
    return entries
      .sort((a, b) => {
        if (a.isDirectory() !== b.isDirectory()) {
          return a.isDirectory() ? -1 : 1;
        }
        return a.name.localeCompare(b.name);
      })
      .map((e) => new FileItem(path.join(dir, e.name), e.isDirectory() ? "dir" : "file"));
  }

  getChildren(element?: FileItem): FileItem[] {
    return this.listDir(element ? element.fsPath : this.outDir);
  }
}
