import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { NodeViewProvider, FileItem } from "./nodeViewProvider";

type ClipboardEntry = { fsPath: string; mode: "copy" | "cut" };

let clipboard: ClipboardEntry | undefined;

const NODE_FILE_MIME_TYPE = "application/vnd.code.tree.fatassnode";

function dirFor(item: FileItem | undefined, nodeViewProvider: NodeViewProvider): string {
  if (!item) {
    return nodeViewProvider.getBaseDir();
  }
  return item.contextValue === "dir" || item.contextValue === "root"
    ? item.fsPath
    : path.dirname(item.fsPath);
}

function uniqueDestination(destDir: string, name: string): string {
  const ext = path.extname(name);
  const base = ext ? name.slice(0, -ext.length) : name;
  let candidate = path.join(destDir, name);
  let n = 2;
  while (fs.existsSync(candidate)) {
    candidate = path.join(destDir, `${base} copy ${n}${ext}`);
    n++;
  }
  return candidate;
}

/**
 * Drag-and-drop for the Node view's own file listing -- dragging an entry
 * onto a folder (or the root row, for the node's own directory) moves it
 * there, same as cut+paste. Dragging files in from the OS file explorer
 * (or another VS Code window) instead copies them in, since there's no
 * "original" location within this tree to remove them from -- VS Code
 * exposes those as a plain "text/uri-list" transfer rather than the
 * internal FileItem-carrying mime type used for drags that originate here.
 */
export class NodeDragAndDropController implements vscode.TreeDragAndDropController<FileItem> {
  readonly dragMimeTypes = [NODE_FILE_MIME_TYPE];
  readonly dropMimeTypes = [NODE_FILE_MIME_TYPE, "text/uri-list"];

  constructor(
    private readonly nodeViewProvider: NodeViewProvider,
    private readonly refresh: () => void
  ) {}

  handleDrag(source: readonly FileItem[], dataTransfer: vscode.DataTransfer): void {
    const items = source.filter((item) => item.contextValue !== "root");
    dataTransfer.set(NODE_FILE_MIME_TYPE, new vscode.DataTransferItem(items));
  }

  async handleDrop(target: FileItem | undefined, dataTransfer: vscode.DataTransfer): Promise<void> {
    const destDir = dirFor(target, this.nodeViewProvider);
    let changed = false;

    const internal = dataTransfer.get(NODE_FILE_MIME_TYPE);
    if (internal) {
      const sources = internal.value as FileItem[];
      for (const source of sources) {
        if (path.dirname(source.fsPath) === destDir || destDir.startsWith(source.fsPath + path.sep)) {
          continue;
        }
        const dest = uniqueDestination(destDir, path.basename(source.fsPath));
        await vscode.workspace.fs.rename(vscode.Uri.file(source.fsPath), vscode.Uri.file(dest));
        changed = true;
      }
    }

    const uriList = await dataTransfer.get("text/uri-list")?.asString();
    if (uriList) {
      for (const line of uriList.split("\n").map((l) => l.trim()).filter((l) => l && !l.startsWith("#"))) {
        const srcPath = vscode.Uri.parse(line).fsPath;
        if (!fs.existsSync(srcPath) || srcPath === destDir) {
          continue;
        }
        const dest = uniqueDestination(destDir, path.basename(srcPath));
        fs.cpSync(srcPath, dest, { recursive: true });
        changed = true;
      }
    }

    if (changed) {
      this.refresh();
    }
  }
}

/** Registers file-management commands for the Node view -- the
 * same operations the native file explorer offers (new file/folder,
 * rename, delete, cut/copy/paste, copy path, open to the side). */
export function registerFileOps(
  context: vscode.ExtensionContext,
  root: string,
  nodeViewProvider: NodeViewProvider
): void {
  const refresh = () => nodeViewProvider.refresh();

  context.subscriptions.push(
    vscode.commands.registerCommand("fatass.newFile", async (item?: FileItem) => {
      const dir = dirFor(item, nodeViewProvider);
      const name = await vscode.window.showInputBox({ prompt: `New file in ${dir}` });
      if (!name) {
        return;
      }
      const target = path.join(dir, name);
      if (fs.existsSync(target)) {
        vscode.window.showErrorMessage(`${name} already exists.`);
        return;
      }
      await vscode.workspace.fs.writeFile(vscode.Uri.file(target), new Uint8Array());
      refresh();
      vscode.commands.executeCommand("vscode.open", vscode.Uri.file(target));
    }),

    vscode.commands.registerCommand("fatass.newFolder", async (item?: FileItem) => {
      const dir = dirFor(item, nodeViewProvider);
      const name = await vscode.window.showInputBox({ prompt: `New folder in ${dir}` });
      if (!name) {
        return;
      }
      const target = path.join(dir, name);
      if (fs.existsSync(target)) {
        vscode.window.showErrorMessage(`${name} already exists.`);
        return;
      }
      await vscode.workspace.fs.createDirectory(vscode.Uri.file(target));
      refresh();
    }),

    vscode.commands.registerCommand("fatass.rename", async (item: FileItem) => {
      const oldName = path.basename(item.fsPath);
      const newName = await vscode.window.showInputBox({
        prompt: `Rename ${oldName}`,
        value: oldName,
      });
      if (!newName || newName === oldName) {
        return;
      }
      const target = path.join(path.dirname(item.fsPath), newName);
      if (fs.existsSync(target)) {
        vscode.window.showErrorMessage(`${newName} already exists.`);
        return;
      }
      await vscode.workspace.fs.rename(vscode.Uri.file(item.fsPath), vscode.Uri.file(target));
      refresh();
    }),

    vscode.commands.registerCommand("fatass.delete", async (item: FileItem) => {
      const name = path.basename(item.fsPath);
      const confirm = await vscode.window.showWarningMessage(
        `Delete ${name}?`,
        { modal: true },
        "Move to Recycle Bin"
      );
      if (confirm !== "Move to Recycle Bin") {
        return;
      }
      await vscode.workspace.fs.delete(vscode.Uri.file(item.fsPath), {
        recursive: true,
        useTrash: true,
      });
      refresh();
    }),

    vscode.commands.registerCommand("fatass.copyPath", (item: FileItem) => {
      vscode.env.clipboard.writeText(item.fsPath);
    }),

    vscode.commands.registerCommand("fatass.copyRelativePath", (item: FileItem) => {
      vscode.env.clipboard.writeText(path.relative(root, item.fsPath).split(path.sep).join("/"));
    }),

    vscode.commands.registerCommand("fatass.openToSide", (item: FileItem) => {
      vscode.commands.executeCommand("vscode.open", vscode.Uri.file(item.fsPath), {
        viewColumn: vscode.ViewColumn.Beside,
      });
    }),

    vscode.commands.registerCommand("fatass.cutFile", (item: FileItem) => {
      clipboard = { fsPath: item.fsPath, mode: "cut" };
    }),

    vscode.commands.registerCommand("fatass.copyFile", (item: FileItem) => {
      clipboard = { fsPath: item.fsPath, mode: "copy" };
    }),

    vscode.commands.registerCommand("fatass.pasteFile", async (item?: FileItem) => {
      if (!clipboard) {
        return;
      }
      const destDir = dirFor(item, nodeViewProvider);
      const target = uniqueDestination(destDir, path.basename(clipboard.fsPath));
      if (clipboard.mode === "cut") {
        await vscode.workspace.fs.rename(vscode.Uri.file(clipboard.fsPath), vscode.Uri.file(target));
        clipboard = undefined;
      } else {
        fs.cpSync(clipboard.fsPath, target, { recursive: true });
      }
      refresh();
    })
  );
}
