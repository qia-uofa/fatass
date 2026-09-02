import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { homeDir, topologyDir } from "./workspaceRoot";
import { NodeItem } from "./topologyProvider";

export type ContentSource = "home" | "topology";

export class FileItem extends vscode.TreeItem {
  constructor(public readonly fsPath: string, isDir: boolean) {
    super(
      path.basename(fsPath),
      isDir ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None
    );
    this.contextValue = isDir ? "dir" : "file";
    this.resourceUri = vscode.Uri.file(fsPath);
    if (!isDir) {
      this.command = {
        command: "fatass.openFile",
        title: "Open",
        arguments: [this],
      };
      this.iconPath = vscode.ThemeIcon.File;
    } else {
      this.iconPath = vscode.ThemeIcon.Folder;
    }
  }
}

export class ContentProvider implements vscode.TreeDataProvider<FileItem> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<FileItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private selectedNode: NodeItem | undefined;
  private source: ContentSource = "home";

  constructor(private readonly root: string) {}

  setSelectedNode(node: NodeItem): void {
    this.selectedNode = node;
    this.refresh();
  }

  toggleSource(): void {
    this.source = this.source === "home" ? "topology" : "home";
    this.refresh();
  }

  getSource(): ContentSource {
    return this.source;
  }

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  private baseDirFor(node: NodeItem): string {
    if (this.source === "topology") {
      return node.dirPath;
    }
    const rel = node.dotPath ? node.dotPath.split(".").join(path.sep) : "";
    return path.join(homeDir(this.root), rel);
  }

  getTreeItem(element: FileItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: FileItem): FileItem[] {
    let dir: string;
    if (element) {
      dir = element.fsPath;
    } else if (this.selectedNode) {
      dir = this.baseDirFor(this.selectedNode);
    } else {
      return [];
    }

    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return [];
    }
    return entries
      .filter((e) => e.name !== "__pycache__")
      .sort((a, b) => {
        if (a.isDirectory() !== b.isDirectory()) {
          return a.isDirectory() ? -1 : 1;
        }
        return a.name.localeCompare(b.name);
      })
      .map((e) => new FileItem(path.join(dir, e.name), e.isDirectory()));
  }
}
