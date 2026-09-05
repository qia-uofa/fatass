"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.registerFileOps = registerFileOps;
const fs = require("fs");
const path = require("path");
const vscode = require("vscode");
let clipboard;
function dirFor(item, nodeViewProvider) {
    if (!item) {
        return nodeViewProvider.getBaseDir();
    }
    return item.contextValue === "dir" || item.contextValue === "root"
        ? item.fsPath
        : path.dirname(item.fsPath);
}
function uniqueDestination(destDir, name) {
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
function registerFileOps(context, root, nodeViewProvider) {
    const refresh = () => nodeViewProvider.refresh();
    context.subscriptions.push(vscode.commands.registerCommand("fatass.newFile", async (item) => {
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
        vscode.window.showTextDocument(vscode.Uri.file(target));
    }), vscode.commands.registerCommand("fatass.newFolder", async (item) => {
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
    }), vscode.commands.registerCommand("fatass.rename", async (item) => {
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
    }), vscode.commands.registerCommand("fatass.delete", async (item) => {
        const name = path.basename(item.fsPath);
        const confirm = await vscode.window.showWarningMessage(`Delete ${name}?`, { modal: true }, "Move to Recycle Bin");
        if (confirm !== "Move to Recycle Bin") {
            return;
        }
        await vscode.workspace.fs.delete(vscode.Uri.file(item.fsPath), {
            recursive: true,
            useTrash: true,
        });
        refresh();
    }), vscode.commands.registerCommand("fatass.copyPath", (item) => {
        vscode.env.clipboard.writeText(item.fsPath);
    }), vscode.commands.registerCommand("fatass.copyRelativePath", (item) => {
        vscode.env.clipboard.writeText(path.relative(root, item.fsPath).split(path.sep).join("/"));
    }), vscode.commands.registerCommand("fatass.openToSide", (item) => {
        vscode.window.showTextDocument(vscode.Uri.file(item.fsPath), {
            viewColumn: vscode.ViewColumn.Beside,
        });
    }), vscode.commands.registerCommand("fatass.cutFile", (item) => {
        clipboard = { fsPath: item.fsPath, mode: "cut" };
    }), vscode.commands.registerCommand("fatass.copyFile", (item) => {
        clipboard = { fsPath: item.fsPath, mode: "copy" };
    }), vscode.commands.registerCommand("fatass.pasteFile", async (item) => {
        if (!clipboard) {
            return;
        }
        const destDir = dirFor(item, nodeViewProvider);
        const target = uniqueDestination(destDir, path.basename(clipboard.fsPath));
        if (clipboard.mode === "cut") {
            await vscode.workspace.fs.rename(vscode.Uri.file(clipboard.fsPath), vscode.Uri.file(target));
            clipboard = undefined;
        }
        else {
            fs.cpSync(clipboard.fsPath, target, { recursive: true });
        }
        refresh();
    }));
}
//# sourceMappingURL=fileOps.js.map