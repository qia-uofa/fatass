import * as vscode from "vscode";
import { findFatassRoot } from "./workspaceRoot";
import { TopologyProvider, NodeItem } from "./topologyProvider";
import { ContentProvider, FileItem } from "./contentProvider";
import { runFatass } from "./runFatass";

export function activate(context: vscode.ExtensionContext): void {
  const root = findFatassRoot();
  if (!root) {
    return;
  }

  const topologyProvider = new TopologyProvider(root);
  const contentProvider = new ContentProvider(root);

  context.subscriptions.push(
    vscode.window.registerTreeDataProvider("fatassTopology", topologyProvider),
    vscode.window.registerTreeDataProvider("fatassContent", contentProvider)
  );

  const nodePathArg = (node: NodeItem) => (node.dotPath ? node.dotPath : "~");

  context.subscriptions.push(
    vscode.commands.registerCommand("fatass.refreshTopology", () => topologyProvider.refresh()),

    vscode.commands.registerCommand("fatass.toggleContentSource", () => contentProvider.toggleSource()),

    vscode.commands.registerCommand("fatass.selectNode", (node: NodeItem) =>
      contentProvider.setSelectedNode(node)
    ),

    vscode.commands.registerCommand("fatass.cd", (node: NodeItem) =>
      runFatass(root, ["cd", nodePathArg(node)])
    ),

    vscode.commands.registerCommand("fatass.run", (node: NodeItem) =>
      runFatass(root, ["run", nodePathArg(node)])
    ),

    vscode.commands.registerCommand("fatass.build", (node: NodeItem) =>
      runFatass(root, ["build", nodePathArg(node)])
    ),

    vscode.commands.registerCommand("fatass.modify", async (node: NodeItem) => {
      const prompt = await vscode.window.showInputBox({
        prompt: `Instructions for modifying ${nodePathArg(node)}`,
        placeHolder: "leave empty to wait for further input",
      });
      if (prompt === undefined) {
        return;
      }
      const args = ["modify", nodePathArg(node)];
      if (prompt) {
        args.push(prompt);
      }
      runFatass(root, args);
    }),

    vscode.commands.registerCommand("fatass.create", async (node: NodeItem) => {
      const child = await vscode.window.showInputBox({
        prompt: `New node/transform under ${nodePathArg(node)} (e.g. "child" or "build")`,
      });
      if (!child) {
        return;
      }
      const base = nodePathArg(node);
      const target = base === "~" ? child : `${base}.${child}`;
      runFatass(root, ["create", target]);
    }),

    vscode.commands.registerCommand("fatass.move", async (node: NodeItem) => {
      const dest = await vscode.window.showInputBox({
        prompt: `Move ${nodePathArg(node)} to...`,
      });
      if (!dest) {
        return;
      }
      runFatass(root, ["move", nodePathArg(node), dest]);
    }),

    vscode.commands.registerCommand("fatass.copy", async (node: NodeItem) => {
      const dest = await vscode.window.showInputBox({
        prompt: `Copy ${nodePathArg(node)} to...`,
      });
      if (!dest) {
        return;
      }
      runFatass(root, ["copy", nodePathArg(node), dest]);
    }),

    vscode.commands.registerCommand("fatass.remove", async (node: NodeItem) => {
      const confirm = await vscode.window.showWarningMessage(
        `Remove ${nodePathArg(node)}?`,
        { modal: true },
        "Remove"
      );
      if (confirm !== "Remove") {
        return;
      }
      runFatass(root, ["remove", nodePathArg(node)]);
    }),

    vscode.commands.registerCommand("fatass.purge", async (node: NodeItem) => {
      const confirm = await vscode.window.showWarningMessage(
        `Purge home/ content for ${nodePathArg(node)}?`,
        { modal: true },
        "Purge"
      );
      if (confirm !== "Purge") {
        return;
      }
      runFatass(root, ["purge", nodePathArg(node)]);
    }),

    vscode.commands.registerCommand("fatass.vim", (node: NodeItem) =>
      runFatass(root, ["vim", nodePathArg(node)])
    ),

    vscode.commands.registerCommand("fatass.openFile", (file: FileItem) => {
      vscode.window.showTextDocument(vscode.Uri.file(file.fsPath));
    }),

    vscode.commands.registerCommand("fatass.revealInExplorer", (file: FileItem) => {
      if (file) {
        vscode.commands.executeCommand("revealFileInOS", vscode.Uri.file(file.fsPath));
      }
    })
  );
}

export function deactivate(): void {}
