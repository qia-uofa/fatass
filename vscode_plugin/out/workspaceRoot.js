"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.findFatassRoot = findFatassRoot;
exports.topologyDir = topologyDir;
exports.homeDir = homeDir;
exports.envPath = envPath;
exports.readCurrentNode = readCurrentNode;
const fs = require("fs");
const path = require("path");
const vscode = require("vscode");
/** Finds the fatass project root: a workspace folder containing fatass/topology. */
function findFatassRoot() {
    const folders = vscode.workspace.workspaceFolders;
    if (!folders) {
        return undefined;
    }
    for (const folder of folders) {
        const candidate = folder.uri.fsPath;
        if (fs.existsSync(path.join(candidate, "fatass", "topology"))) {
            return candidate;
        }
    }
    return undefined;
}
function topologyDir(root) {
    return path.join(root, "fatass", "topology");
}
function homeDir(root) {
    return path.join(root, "home");
}
const FATASS_ROOT_SENTINEL = "~";
/** Path (relative to `.fatass/.env`) of the FATASS_NODE dotenv file. */
function envPath(root) {
    return path.join(root, ".fatass", ".env");
}
/**
 * Reads the current node (`FATASS_NODE`) from `.fatass/.env`, the same
 * plain KEY=VALUE dotenv format `fatass.resolve.dotenv` writes: "" (the
 * true topology root) if the file or variable is missing.
 */
function readCurrentNode(root) {
    const file = envPath(root);
    if (!fs.existsSync(file)) {
        return "";
    }
    const text = fs.readFileSync(file, "utf-8");
    for (const rawLine of text.split(/\r?\n/)) {
        const line = rawLine.trim();
        if (!line || line.startsWith("#") || !line.includes("=")) {
            continue;
        }
        const [key, ...rest] = line.split("=");
        if (key.trim() !== "FATASS_NODE") {
            continue;
        }
        let value = rest.join("=").trim();
        if (value.length >= 2 && value[0] === value[value.length - 1] && (value[0] === '"' || value[0] === "'")) {
            value = value.slice(1, -1);
        }
        return value === FATASS_ROOT_SENTINEL ? "" : value;
    }
    return "";
}
//# sourceMappingURL=workspaceRoot.js.map