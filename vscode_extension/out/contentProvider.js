"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ContentProvider = exports.FileItem = void 0;
exports.nodeTitle = nodeTitle;
const fs = require("fs");
const path = require("path");
const vscode = require("vscode");
const workspaceRoot_1 = require("./workspaceRoot");
function toPascalCase(name) {
    return name
        .split(/[_-]+/)
        .filter(Boolean)
        .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
        .join("");
}
/** "NodeName(NodeClass)" for a dotted node path, e.g. "materials(Materials)"; root is "~(topology)". */
function nodeTitle(dotPath) {
    if (!dotPath) {
        return "~(topology)";
    }
    const name = dotPath.split(".").pop();
    return `${name}(${toPascalCase(name)})`;
}
/**
 * A row in the Node Content view. `kind === "root"` is a synthetic entry
 * (not a real child of the listed directory) standing in for the
 * currently-displayed node's home/topology dir itself -- without it,
 * there was nothing to right-click to reach root-level actions (new
 * file/folder, paste, reveal in topology) except blank space below the
 * real listing, and right-clicking blank space in a vscode TreeView
 * reuses whatever was last *selected* rather than meaning "nothing" --
 * so a stale selection could make a blank-area right-click look like it
 * "redirected" to some earlier item. Giving the root dir a real,
 * always-visible item removes the need to rely on blank space for those
 * actions at all.
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
        else {
            // Matches NodeItem's own icon in the Topology view -- this row
            // stands in for the same node, just from the content side.
            this.iconPath = new vscode.ThemeIcon("symbol-class");
        }
    }
}
exports.FileItem = FileItem;
/** Shows the current node's (`FATASS_NODE`, from `.fatass/.env`) files. */
class ContentProvider {
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
    getChildren(element) {
        if (!element) {
            return [new FileItem(this.getBaseDir(), "root", nodeTitle(this.currentPath))];
        }
        const dir = element.fsPath;
        let entries;
        try {
            entries = fs.readdirSync(dir, { withFileTypes: true });
        }
        catch {
            return [];
        }
        return entries
            .filter((e) => e.name !== "__pycache__" && !e.name.startsWith("."))
            .sort((a, b) => {
            if (a.isDirectory() !== b.isDirectory()) {
                return a.isDirectory() ? -1 : 1;
            }
            return a.name.localeCompare(b.name);
        })
            .map((e) => new FileItem(path.join(dir, e.name), e.isDirectory() ? "dir" : "file"));
    }
}
exports.ContentProvider = ContentProvider;
//# sourceMappingURL=contentProvider.js.map