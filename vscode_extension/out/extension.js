"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = require("vscode");
const workspaceRoot_1 = require("./workspaceRoot");
const topologyProvider_1 = require("./topologyProvider");
const nodeViewProvider_1 = require("./nodeViewProvider");
const runFatass_1 = require("./runFatass");
const fileOps_1 = require("./fileOps");
function activate(context) {
    const root = (0, workspaceRoot_1.findFatassRoot)();
    if (!root) {
        return;
    }
    const topologyProvider = new topologyProvider_1.TopologyProvider(root);
    const nodeViewProvider = new nodeViewProvider_1.NodeViewProvider(root);
    // Always absolute ("~."-prefixed) -- FATASS_NODE (the fatass "pwd") can be
    // anywhere, and a bare dotted path resolves relative to it, not to root.
    const nodePathArg = (node) => (node.dotPath ? `~.${node.dotPath}` : "~");
    const refreshAll = () => {
        topologyProvider.refresh();
        nodeViewProvider.syncCurrentNode();
    };
    // Runs a fatass command directly, no confirmation -- used only for `cd`,
    // which is just navigation and changes nothing outside `.fatass/.env`.
    const runNoConfirm = (args) => (0, runFatass_1.runFatass)(root, args, refreshAll);
    // Every other context-menu command that shells out to fatass confirms
    // first, showing the exact command line it's about to run (verbatim,
    // including quoting) rather than a paraphrased description of the
    // action.
    const run = async (node, args) => {
        const commandLine = (0, runFatass_1.fatassCommandLine)(args);
        const confirm = await vscode.window.showWarningMessage(commandLine, { modal: true }, "Run");
        if (confirm !== "Run") {
            return;
        }
        runNoConfirm(args);
    };
    // Dropping a node onto another node reparents it there, keeping its own
    // leaf name (the "*" destination shorthand -- see `fatass move`'s own
    // docs) -- dropping onto the tree's blank area (target undefined) moves
    // it to the top level. A drop onto itself, into its own subtree, or back
    // onto its current parent is a silent no-op / a clear error rather than
    // an actual `fatass move` call, since that command itself would either
    // reject it (own subtree) or do nothing useful (current parent).
    const moveNode = (source, target) => {
        const targetDotPath = target ? target.dotPath : "";
        if (targetDotPath === source.dotPath || targetDotPath.startsWith(`${source.dotPath}.`)) {
            vscode.window.showErrorMessage(`Can't move ${source.dotPath || "~"} into itself or its own subtree.`);
            return;
        }
        const currentParent = source.dotPath.includes(".")
            ? source.dotPath.slice(0, source.dotPath.lastIndexOf("."))
            : "";
        if (targetDotPath === currentParent) {
            return;
        }
        const dest = targetDotPath ? `~.${targetDotPath}.*` : "~.*";
        run(source, ["move", nodePathArg(source), dest]);
    };
    const topologyView = vscode.window.createTreeView("fatassTopology", {
        treeDataProvider: topologyProvider,
        dragAndDropController: new topologyProvider_1.TopologyDragAndDropController(moveNode),
    });
    const nodeView = vscode.window.createTreeView("fatassNode", {
        treeDataProvider: nodeViewProvider,
    });
    // The view's own title stays the static "Node" (matching the Topology
    // view's own static title) -- the current node and home/topology
    // toggle live in the description instead, and never mention the
    // node's class (that's the Topology view's job).
    const updateNodeViewTitle = () => {
        nodeView.description = `${(0, nodeViewProvider_1.nodeLabel)(nodeViewProvider.getCurrentPath())} · ${nodeViewProvider.getSource() === "home" ? "Home" : "Topology"}`;
    };
    updateNodeViewTitle();
    nodeViewProvider.onDidChangeTreeData(updateNodeViewTitle);
    // The Node view always tracks FATASS_NODE (the fatass "pwd"), not
    // tree-click selection, so it must be re-read whenever .fatass/.env
    // changes -- including edits made from outside this extension (a plain
    // terminal `fatass cd`, `fatass shell`, etc).
    const envWatcher = vscode.workspace.createFileSystemWatcher(new vscode.RelativePattern(root, ".fatass/.env"));
    const syncPwd = () => nodeViewProvider.syncCurrentNode();
    envWatcher.onDidChange(syncPwd);
    envWatcher.onDidCreate(syncPwd);
    envWatcher.onDidDelete(syncPwd);
    context.subscriptions.push(topologyView, nodeView, envWatcher);
    (0, fileOps_1.registerFileOps)(context, root, nodeViewProvider);
    context.subscriptions.push(vscode.commands.registerCommand("fatass.refreshTopology", () => topologyProvider.refresh()), vscode.commands.registerCommand("fatass.toggleNodeViewSource", () => nodeViewProvider.toggleSource()), 
    // Context-menu "cd": typed into the active terminal, same as every
    // other confirmed command -- bare "cd ..." if that terminal is sitting
    // inside the REPL, else the full "python -m fatass cd ...".
    vscode.commands.registerCommand("fatass.cd", (node) => {
        runNoConfirm(["cd", nodePathArg(node)]);
        // The REPL's own `cd` is in-memory only (see shell.py's
        // enter_session) -- it never touches .fatass/.env, so
        // syncCurrentNode() (via runNoConfirm's onDone) would never see it.
        // We already know the target here, so mirror it directly instead.
        if ((0, runFatass_1.isInShellRepl)()) {
            nodeViewProvider.setCurrentPath(node.dotPath);
        }
    }), 
    // The Topology view's inline "->" button: applies silently in the
    // background regardless of terminal state -- never typed into a
    // terminal, unlike the context-menu "cd" above.
    vscode.commands.registerCommand("fatass.cdBackground", (node) => {
        (0, runFatass_1.runFatassBackground)(root, ["cd", nodePathArg(node)], refreshAll);
    }), vscode.commands.registerCommand("fatass.run", (node) => run(node, ["run", nodePathArg(node)])), vscode.commands.registerCommand("fatass.build", (node) => run(node, ["build", nodePathArg(node)])), vscode.commands.registerCommand("fatass.modify", async (node) => {
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
        run(node, args);
    }), vscode.commands.registerCommand("fatass.create", async (node) => {
        const child = await vscode.window.showInputBox({
            prompt: `New node/transform under ${nodePathArg(node)} (e.g. "child" or "build")`,
        });
        if (!child) {
            return;
        }
        const base = nodePathArg(node);
        const target = base === "~" ? `~.${child}` : `${base}.${child}`;
        run(node, ["create", target]);
    }), vscode.commands.registerCommand("fatass.move", async (node) => {
        const dest = await vscode.window.showInputBox({
            prompt: `Move ${nodePathArg(node)} to...`,
        });
        if (!dest) {
            return;
        }
        run(node, ["move", nodePathArg(node), dest]);
    }), vscode.commands.registerCommand("fatass.copy", async (node) => {
        const dest = await vscode.window.showInputBox({
            prompt: `Copy ${nodePathArg(node)} to...`,
        });
        if (!dest) {
            return;
        }
        run(node, ["copy", nodePathArg(node), dest]);
    }), vscode.commands.registerCommand("fatass.remove", (node) => run(node, ["remove", nodePathArg(node)])), vscode.commands.registerCommand("fatass.purge", (node) => run(node, ["purge", nodePathArg(node)])), vscode.commands.registerCommand("fatass.vim", (node) => run(node, ["vim", nodePathArg(node)])), vscode.commands.registerCommand("fatass.openFile", (file) => {
        vscode.commands.executeCommand("vscode.open", vscode.Uri.file(file.fsPath));
    }), vscode.commands.registerCommand("fatass.revealInExplorer", (file) => {
        if (file) {
            vscode.commands.executeCommand("revealFileInOS", vscode.Uri.file(file.fsPath));
        }
    }), 
    // Always targets the node the Node view is currently showing
    // (FATASS_NODE), not whichever specific file/dir was right-clicked --
    // a nested file's own directory isn't necessarily a topology node at
    // all (it could just be a plain subdirectory of assets), so "the
    // node this content belongs to" is the only reliably meaningful
    // target here. Scrolls the Topology view to it without selecting/
    // highlighting it or stealing focus -- reveal() scrolls regardless.
    vscode.commands.registerCommand("fatass.revealInTopology", async () => {
        const target = topologyProvider.nodeItemForPath(nodeViewProvider.getCurrentPath());
        await topologyView.reveal(target, { select: false, focus: false, expand: true });
    }));
}
function deactivate() { }
//# sourceMappingURL=extension.js.map