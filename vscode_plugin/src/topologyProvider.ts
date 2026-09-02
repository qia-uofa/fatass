import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { isNodeDir, topologyDir } from "./workspaceRoot";

/** One node in the fatass topology tree (dotted path + real directory). */
export class NodeItem extends vscode.TreeItem {
  constructor(
    public readonly dotPath: string,
    public readonly dirPath: string,
    hasChildren: boolean
  ) {
    super(
      path.basename(dirPath),
      hasChildren
        ? vscode.TreeItemCollapsibleState.Collapsed
        : vscode.TreeItemCollapsibleState.None
    );
    this.contextValue = "node";
    this.tooltip = dotPath || "~";
    this.iconPath = new vscode.ThemeIcon("symbol-class");
    this.command = {
      command: "fatass.selectNode",
      title: "Select fatass node",
      arguments: [this],
    };
  }
}

function childNodeDirs(dir: string): string[] {
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return [];
  }
  return entries
    .filter((e) => e.isDirectory() && !e.name.startsWith("__") && e.name !== "transforms")
    .map((e) => path.join(dir, e.name))
    .filter(isNodeDir)
    .sort((a, b) => path.basename(a).localeCompare(path.basename(b)));
}

export class TopologyProvider implements vscode.TreeDataProvider<NodeItem> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<NodeItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private readonly root: string) {}

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: NodeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: NodeItem): NodeItem[] {
    const baseDir = element ? element.dirPath : topologyDir(this.root);
    return childNodeDirs(baseDir).map((dir) => {
      const dotPath = path.relative(topologyDir(this.root), dir).split(path.sep).join(".");
      return new NodeItem(dotPath, dir, childNodeDirs(dir).length > 0);
    });
  }
}
