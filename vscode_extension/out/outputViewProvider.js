"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.OutputViewProvider = void 0;
const fs = require("fs");
const path = require("path");
const vscode = require("vscode");
const nodeViewProvider_1 = require("./nodeViewProvider");
/** Plain, read-only browser for `out/` (see `fatass._internal.paths.
 * OUT_ROOT`) -- the dispatch log and `fatass graph`'s own default `.puml`
 * output, and anywhere else a future command writes something meant for a
 * human to read rather than a node's own `home/` content. No "current
 * node" concept here (unlike the Node view) -- one fixed root, so no
 * synthetic "root" wrapper row is needed either. */
class OutputViewProvider {
    constructor(root) {
        this._onDidChangeTreeData = new vscode.EventEmitter();
        this.onDidChangeTreeData = this._onDidChangeTreeData.event;
        this.outDir = path.join(root, "out");
    }
    refresh() {
        this._onDidChangeTreeData.fire();
    }
    getTreeItem(element) {
        return element;
    }
    listDir(dir) {
        let entries;
        try {
            entries = fs.readdirSync(dir, { withFileTypes: true });
        }
        catch {
            return [];
        }
        return entries
            .sort((a, b) => {
            if (a.isDirectory() !== b.isDirectory()) {
                return a.isDirectory() ? -1 : 1;
            }
            return a.name.localeCompare(b.name);
        })
            .map((e) => new nodeViewProvider_1.FileItem(path.join(dir, e.name), e.isDirectory() ? "dir" : "file"));
    }
    getChildren(element) {
        return this.listDir(element ? element.fsPath : this.outDir);
    }
}
exports.OutputViewProvider = OutputViewProvider;
//# sourceMappingURL=outputViewProvider.js.map