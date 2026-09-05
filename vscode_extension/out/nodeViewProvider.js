"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.NodeViewProvider = exports.FileItem = void 0;
exports.nodeLabel = nodeLabel;
const fs = require("fs");
const path = require("path");
const vscode = require("vscode");
const workspaceRoot_1 = require("./workspaceRoot");
/** Label for a dotted node path, e.g. "materials" for "roster.materials"; root is "~". No class name here -- that's the Topology view's job. */
function nodeLabel(dotPath) {
    return dotPath ? dotPath.split(".").pop() : "~";
}
function sortEntries(a, b) {
    if (a.isDirectory() !== b.isDirectory()) {
        return a.isDirectory() ? -1 : 1;
    }
    return a.name.localeCompare(b.name);
}
/** Depth-`i` `.next`-chain directory under a Chain node's own home dir --
 * see fatass.Chain: item i lives i+1 `.next` levels down. */
function chainItemDir(baseDir, index) {
    return path.join(baseDir, ...Array(index + 1).fill(".next"));
}
/** How many chain items exist directly under `baseDir` (0 if it isn't a
 * Chain's home dir at all) -- counts `.next` levels rather than asking
 * fatass, since this is purely a filesystem walk. */
function chainLength(baseDir) {
    let length = 0;
    let cur = path.join(baseDir, ".next");
    while (fs.existsSync(cur)) {
        length++;
        cur = path.join(cur, ".next");
    }
    return length;
}
/**
 * A row in the Node view. `kind === "root"` is a synthetic entry (not a
 * real child of the listed directory) standing in for the
 * currently-displayed node's home/topology dir itself -- without it,
 * there was nothing to right-click to reach root-level actions (new
 * file/folder, paste, reveal in topology) except blank space below the
 * real listing, and right-clicking blank space in a vscode TreeView
 * reuses whatever was last *selected* rather than meaning "nothing" --
 * so a stale selection could make a blank-area right-click look like it
 * "redirected" to some earlier item. Giving the root dir a real,
 * always-visible item removes the need to rely on blank space for those
 * actions at all.
 *
 * `kind === "chainItem"` is a Chain node's item `i` (see fatass.Chain) --
 * shown as "name[i]" alongside the node's other content rather than the
 * raw `.next` directory nesting.
 */
class FileItem extends vscode.TreeItem {
    constructor(fsPath, kind, label) {
        super(label ?? path.basename(fsPath), kind === "file"
            ? vscode.TreeItemCollapsibleState.None
            : kind === "root"
                ? vscode.TreeItemCollapsibleState.Expanded
                : vscode.TreeItemCollapsibleState.Collapsed);
        this.fsPath = fsPath;
        this.contextValue = kind;
        this.resourceUri = vscode.Uri.file(fsPath);
        if (kind === "file") {
            this.command = {
                command: "fatass.openFile",
                title: "Open",
                arguments: [this],
            };
            this.iconPath = vscode.ThemeIcon.File;
        }
        else if (kind === "dir") {
            this.iconPath = vscode.ThemeIcon.Folder;
        }
        else if (kind === "chainItem") {
            // Same icon as the "root" row for this node -- a chain item is just
            // another instance of the node itself, not a plain subdirectory.
            this.iconPath = new vscode.ThemeIcon("symbol-class");
        }
        else {
            // Matches NodeItem's own icon in the Topology view -- this row
            // stands in for the same node, just from the Node view's side.
            this.iconPath = new vscode.ThemeIcon("symbol-class");
        }
    }
}
exports.FileItem = FileItem;
/** Shows the current node's (`FATASS_NODE`, from `.fatass/.env`) files. */
class NodeViewProvider {
    constructor(root) {
        this.root = root;
        this._onDidChangeTreeData = new vscode.EventEmitter();
        this.onDidChangeTreeData = this._onDidChangeTreeData.event;
        this.currentPath = "";
        this.source = "home";
        this.currentPath = (0, workspaceRoot_1.readCurrentNode)(root);
    }
    /** Re-reads FATASS_NODE from .fatass/.env and refreshes if it changed. */
    syncCurrentNode() {
        const next = (0, workspaceRoot_1.readCurrentNode)(this.root);
        if (next !== this.currentPath) {
            this.currentPath = next;
        }
        this.refresh();
    }
    /** Sets the displayed current node directly, bypassing .fatass/.env --
     * for a `cd` sent into a running `fatass shell` REPL, whose own `cd`
     * deliberately never writes that file (so it doesn't leak into other
     * processes/sessions), so `syncCurrentNode()` would never see it. */
    setCurrentPath(dotPath) {
        this.currentPath = dotPath;
        this.refresh();
    }
    toggleSource() {
        this.source = this.source === "home" ? "topology" : "home";
        this.refresh();
    }
    getSource() {
        return this.source;
    }
    getCurrentPath() {
        return this.currentPath;
    }
    refresh() {
        this._onDidChangeTreeData.fire();
    }
    /** Directory currently shown at the root of this view (per FATASS_NODE + home/topology toggle). */
    getBaseDir() {
        const rel = this.currentPath ? this.currentPath.split(".").join(path.sep) : "";
        return this.source === "topology" ? path.join((0, workspaceRoot_1.topologyDir)(this.root), rel) : path.join((0, workspaceRoot_1.homeDir)(this.root), rel);
    }
    getTreeItem(element) {
        return element;
    }
    /** Plain directory listing -- reserved/placeholder entries excluded (see
     * `HIDDEN_NAMES`), dirs before files, alphabetical within each. */
    listDir(dir) {
        let entries;
        try {
            entries = fs.readdirSync(dir, { withFileTypes: true });
        }
        catch {
            return [];
        }
        return entries
            .filter((e) => !NodeViewProvider.HIDDEN_NAMES.has(e.name))
            .sort(sortEntries)
            .map((e) => new FileItem(path.join(dir, e.name), e.isDirectory() ? "dir" : "file"));
    }
    /** A chain item's own content: any schema-child directories at that
     * `.next` depth (structured lists) plus, unwrapped, whatever sits in
     * its reserved `.entry` directory (leaf lists) -- `.next` itself (the
     * next item, not this one's content) is never shown here. */
    listChainItem(dir) {
        const own = this.listDir(dir);
        const entryDir = path.join(dir, ".entry");
        return fs.existsSync(entryDir) ? [...own, ...this.listDir(entryDir)] : own;
    }
    /** Synthetic `chainItem` rows for `dir`'s `.next` chain, if any -- empty
     * when `dir` isn't a Chain's home dir at all, or in the topology (source
     * code) view, where Chain structure never applies. */
    chainItems(dir, label) {
        const length = this.source === "home" ? chainLength(dir) : 0;
        return Array.from({ length }, (_, i) => new FileItem(chainItemDir(dir, i), "chainItem", `${label}[${i}]`));
    }
    /** A directory's regular contents plus, if it's itself a Chain's home
     * dir (or a chain item's own depth -- structured lists can nest a Chain
     * arbitrarily), its `.next` items rendered as synthetic `chainItem` rows
     * alongside them -- siblings of the real entries, never nested under one. */
    listChainAware(dir, label) {
        return [...this.listDir(dir), ...this.chainItems(dir, label)];
    }
    getChildren(element) {
        if (!element) {
            const dir = this.getBaseDir();
            // The "root" row stands in for the current node itself -- its own
            // regular content (schema children, plain files/dirs) nests under
            // it, same as always. Its chain items (if it's a Chain) are each
            // their own instance of that node, not content *of* it, so they sit
            // beside the root row as top-level siblings instead of under it.
            const root = new FileItem(dir, "root", nodeLabel(this.currentPath));
            return [root, ...this.chainItems(dir, nodeLabel(this.currentPath))];
        }
        if (element.contextValue === "chainItem") {
            return this.listChainItem(element.fsPath);
        }
        const dir = element.fsPath;
        if (element.contextValue === "root") {
            return this.listDir(dir);
        }
        return this.listChainAware(dir, path.basename(dir));
    }
}
exports.NodeViewProvider = NodeViewProvider;
/** Names never shown directly -- `.next`/`.entry` are Chain internals
 * rendered specially (see `listChainAware`/`listChainItem`), `.gitkeep`
 * is a git-only placeholder, and `__pycache__` is Python noise. Every
 * other dotfile is shown like any other entry. */
NodeViewProvider.HIDDEN_NAMES = new Set(["__pycache__", ".gitkeep", ".next", ".entry"]);
//# sourceMappingURL=nodeViewProvider.js.map