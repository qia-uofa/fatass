import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { NodeViewProvider, FileItem } from "./nodeViewProvider";

type ClipboardEntry = { fsPath: string; mode: "copy" | "cut" };

let clipboard: ClipboardEntry | undefined;

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
