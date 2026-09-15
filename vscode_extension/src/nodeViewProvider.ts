import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { execFileSync } from "child_process";
import { homeDir, PAREN_ROOT, readCurrentNode, toPascalPath, topologyDir } from "./workspaceRoot";

export type NodeViewSource = "home" | "topology";

// Asks fatass itself whether the current node is a `Dir` and, if so, its
// real resolved directory (`Dir._assets_dir()` -- same call `fatass dir
// path` makes) -- rather than re-parsing its ".path" file and walking
// parent Dir chains here, which would just be a second, independently
// maintained copy of `fatass.node.dir.Dir`'s own PATH/`_resolved_path()`
// resolution logic.
const DIR_INFO_SCRIPT = `
import sys, json
from fatass.core.transform import _import_node
from fatass.node.dir import Dir

def dir_info(path):
    if not path:
        return {"is_dir": False, "resolved": None}
    try:
        cls = _import_node(path)
    except Exception:
        return {"is_dir": False, "resolved": None}
    if not issubclass(cls, Dir):
        return {"is_dir": False, "resolved": None}
    try:
        resolved = str(cls._assets_dir())
    except Exception:
        resolved = None
    return {"is_dir": True, "resolved": resolved}

print(json.dumps(dir_info(sys.argv[1] if len(sys.argv) > 1 else "")))
`;

interface DirInfo {
  isDir: boolean;
  resolved: string | null;
}

function fetchDirInfo(root: string, dotPath: string): DirInfo {
  try {
    const out = execFileSync("python", ["-c", DIR_INFO_SCRIPT, dotPath], {
      cwd: root,
      encoding: "utf8",
    });
    const parsed = JSON.parse(out);
    return { isDir: Boolean(parsed.is_dir), resolved: parsed.resolved ?? null };
  } catch {
    return { isDir: false, resolved: null };
  }
}

/** Label for a dotted node path, e.g. "Materials" for "roster.materials";
 * root is `PAREN_ROOT`. PascalCased to match the node's real class name --
 * no base-class name here, though, that's the Topology view's job. */
export function nodeLabel(dotPath: string): string {
  return dotPath ? toPascalPath(dotPath.split(".").pop()!) : PAREN_ROOT;
}

export type FileItemKind = "file" | "dir" | "root" | "chainItem" | "dictItem" | "homeBranch" | "pathBranch";

function sortEntries(a: fs.Dirent, b: fs.Dirent): number {
  if (a.isDirectory() !== b.isDirectory()) {
    return a.isDirectory() ? -1 : 1;
  }
  return a.name.localeCompare(b.name);
}

/** Depth-`i` `.next`-chain directory under a Chain node's own home dir --
 * see fatass.Chain: item i lives i+1 `.next` levels down. */
function chainItemDir(baseDir: string, index: number): string {
  return path.join(baseDir, ...Array(index + 1).fill(".next"));
}

/** How many chain items exist directly under `baseDir` (0 if it isn't a
 * Chain's home dir at all) -- counts `.next` levels rather than asking
 * fatass, since this is purely a filesystem walk. */
function chainLength(baseDir: string): number {
  let length = 0;
  let cur = path.join(baseDir, ".next");
  while (fs.existsSync(cur)) {
    length++;
    cur = path.join(cur, ".next");
  }
  return length;
}

/** `key`'s own entry directory under a Dictionary node's own home dir --
 * see fatass.Dictionary: flat (unlike Chain's nested `.next`), so this is
 * just `.items/<key>`. */
function dictItemDir(baseDir: string, key: string): string {
  return path.join(baseDir, ".items", key);
}

/** Every key that currently exists under `baseDir`'s `.items` dir ([] if
 * it isn't a Dictionary's home dir at all) -- sorted, matching
 * `fatass.Dictionary.keys()`'s own convention -- a pure filesystem walk,
 * same reasoning as `chainLength`'s own (no need to ask fatass whether
 * this node actually IS a Dictionary; `.items` is a reserved name no
 * plain Node's own content would coincidentally have). */
function dictKeys(baseDir: string): string[] {
  const itemsDir = path.join(baseDir, ".items");
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(itemsDir, { withFileTypes: true });
  } catch {
    return [];
  }
  return entries
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort((a, b) => a.localeCompare(b));
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
 * raw `.next` directory nesting. `kind === "dictItem"` is a Dictionary
 * node's entry for key `k` (see fatass.Dictionary) -- shown as "name[k]"
 * the same way, rather than the raw `.items/<k>` directory.
 */
export class FileItem extends vscode.TreeItem {
  constructor(public readonly fsPath: string, kind: FileItemKind, label?: string) {
    super(
      label ?? path.basename(fsPath),
      kind === "file"
        ? vscode.TreeItemCollapsibleState.None
        : kind === "root"
        ? vscode.TreeItemCollapsibleState.Expanded
        : vscode.TreeItemCollapsibleState.Collapsed
    );
    this.contextValue = kind;
    this.resourceUri = vscode.Uri.file(fsPath);
    if (kind === "file") {
      this.command = {
        command: "fatass.openFile",
        title: "Open",
        arguments: [this],
      };
      this.iconPath = vscode.ThemeIcon.File;
    } else if (kind === "dir" || kind === "homeBranch") {
      this.iconPath = vscode.ThemeIcon.Folder;
    } else if (kind === "pathBranch") {
      // Visually distinct from a plain "dir"/"homeBranch" folder -- this
      // one points at a Dir node's real resolved directory, which can be
      // anywhere on disk, not necessarily under this workspace at all.
      this.iconPath = new vscode.ThemeIcon("link-external");
    } else if (kind === "chainItem" || kind === "dictItem") {
      // Same icon as the "root" row for this node -- a chain/dict item is
      // just another instance of the node itself, not a plain subdirectory.
      this.iconPath = new vscode.ThemeIcon("symbol-class");
    } else {
      // Matches NodeItem's own icon in the Topology view -- this row
      // stands in for the same node, just from the Node view's side.
      this.iconPath = new vscode.ThemeIcon("symbol-class");
    }
  }
}

/** Shows the current node's (`FATASS_NODE`, from `.fatass/.env`) files. */
export class NodeViewProvider implements vscode.TreeDataProvider<FileItem> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<FileItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private currentPath: string = "";
  private source: NodeViewSource = "home";
  private dirInfo: DirInfo = { isDir: false, resolved: null };

  constructor(private readonly root: string) {
    this.currentPath = readCurrentNode(root);
    this.dirInfo = fetchDirInfo(root, this.currentPath);
  }

  /** Re-reads FATASS_NODE from .fatass/.env and refreshes if it changed. */
  syncCurrentNode(): void {
    const next = readCurrentNode(this.root);
    if (next !== this.currentPath) {
      this.currentPath = next;
      this.dirInfo = fetchDirInfo(this.root, this.currentPath);
    }
    this.refresh();
  }

  /** Sets the displayed current node directly, bypassing .fatass/.env --
   * for a `cd` sent into a running `fatass shell` REPL, whose own `cd`
   * deliberately never writes that file (so it doesn't leak into other
   * processes/sessions), so `syncCurrentNode()` would never see it. */
  setCurrentPath(dotPath: string): void {
    this.currentPath = dotPath;
    this.dirInfo = fetchDirInfo(this.root, this.currentPath);
    this.refresh();
  }

  toggleSource(): void {
    this.source = this.source === "home" ? "topology" : "home";
    this.refresh();
  }

  /** Manual refresh, e.g. from the view's own toolbar button -- re-fetches
   * `dirInfo` (so a just-edited ".path" file's new target shows up
   * immediately) and re-renders, without needing FATASS_NODE itself to
   * have changed the way `syncCurrentNode()` requires. */
  refreshAll(): void {
    this.dirInfo = fetchDirInfo(this.root, this.currentPath);
    this.refresh();
  }

  getSource(): NodeViewSource {
    return this.source;
  }

  getCurrentPath(): string {
    return this.currentPath;
  }

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  /** Directory currently shown at the root of this view (per FATASS_NODE +
   * the home/topology toggle). */
  getBaseDir(): string {
    const rel = this.currentPath ? this.currentPath.split(".").join(path.sep) : "";
    return this.source === "topology" ? path.join(topologyDir(this.root), rel) : path.join(homeDir(this.root), rel);
  }

  getTreeItem(element: FileItem): vscode.TreeItem {
    return element;
  }

  /** Names never shown directly -- `.next`/`.entry` are Chain internals and
   * `.items`/`.entry` are Dictionary internals, both rendered specially
   * (see `listCollectionAware`/`listItemContent`), `.gitkeep` is a
   * git-only placeholder, and `__pycache__` is Python noise. Every other
   * dotfile is shown like any other entry. */
  private static readonly HIDDEN_NAMES = new Set(["__pycache__", ".gitkeep", ".next", ".entry", ".items"]);

  /** Plain directory listing -- reserved/placeholder entries excluded (see
   * `HIDDEN_NAMES`), dirs before files, alphabetical within each. */
  private listDir(dir: string): FileItem[] {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return [];
    }
    return entries
      .filter((e) => !NodeViewProvider.HIDDEN_NAMES.has(e.name))
      .sort(sortEntries)
      .map((e) => new FileItem(path.join(dir, e.name), e.isDirectory() ? "dir" : "file"));
  }

  /** A chain/dict item's own content: any schema-child directories at that
   * depth (structured lists/dicts) plus, unwrapped, whatever sits in its
   * reserved `.entry` directory (leaf lists/dicts) -- `.next`/`.items`
   * themselves (a further-nested item, not this one's own content) are
   * never shown here. */
  private listItemContent(dir: string): FileItem[] {
    const own = this.listDir(dir);
    const entryDir = path.join(dir, ".entry");
    return fs.existsSync(entryDir) ? [...own, ...this.listDir(entryDir)] : own;
  }

  /** Synthetic `chainItem` rows for `dir`'s `.next` chain, if any -- empty
   * when `dir` isn't a Chain's home dir at all, or in the topology (source
   * code) view, where Chain structure never applies. */
  private chainItems(dir: string, label: string): FileItem[] {
    const length = this.source === "home" ? chainLength(dir) : 0;
    return Array.from({ length }, (_, i) => new FileItem(chainItemDir(dir, i), "chainItem", `${label}[${i}]`));
  }

  /** Synthetic `dictItem` rows for `dir`'s `.items` entries, if any -- same
   * home-view-only restriction as `chainItems`, for the same reason. */
  private dictItems(dir: string, label: string): FileItem[] {
    const keys = this.source === "home" ? dictKeys(dir) : [];
    return keys.map((key) => new FileItem(dictItemDir(dir, key), "dictItem", `${label}[${key}]`));
  }

  /** A directory's regular contents plus, if it's itself a Chain's home
   * dir (or a chain item's own depth -- structured lists can nest a Chain
   * arbitrarily) and/or a Dictionary's home dir the same way, its `.next`
   * items and/or `.items` entries rendered as synthetic `chainItem`/
   * `dictItem` rows alongside them -- siblings of the real entries, never
   * nested under one. A node is never both at once, but nothing here
   * assumes that -- whichever reserved directory actually exists wins. */
  private listCollectionAware(dir: string, label: string): FileItem[] {
    return [...this.listDir(dir), ...this.chainItems(dir, label), ...this.dictItems(dir, label)];
  }

  getChildren(element?: FileItem): FileItem[] {
    if (!element) {
      const dir = this.getBaseDir();
      // The "root" row stands in for the current node itself -- its own
      // regular content (schema children, plain files/dirs) nests under
      // it, same as always. Its chain/dict items (if it's a Chain or
      // Dictionary) are each their own instance of that node, not content
      // *of* it, so they sit beside the root row as top-level siblings
      // instead of under it.
      const root = new FileItem(dir, "root", nodeLabel(this.currentPath));
      const label = nodeLabel(this.currentPath);
      return [root, ...this.chainItems(dir, label), ...this.dictItems(dir, label)];
    }
    if (element.contextValue === "chainItem" || element.contextValue === "dictItem") {
      return this.listItemContent(element.fsPath);
    }

    const dir = element.fsPath;
    if (element.contextValue === "root") {
      // A Dir node's own home/ dir is just fatass's bookkeeping (its
      // ".path" file, and one near-empty stub per mirrored child Dir) --
      // never the node's real content, which lives at `dirInfo.resolved`
      // instead (possibly outside this workspace entirely). Split into
      // two parallel, clearly-labeled branches rather than picking one
      // or silently merging/hiding either -- nothing about the raw home
      // dir (the ".path" file included) is hidden, it's just one tap
      // away instead of flattened into the top-level listing.
      if (this.source === "home" && this.dirInfo.resolved) {
        return [
          new FileItem(dir, "homeBranch", "Home"),
          new FileItem(this.dirInfo.resolved, "pathBranch", "Path"),
        ];
      }
      return this.listDir(dir);
    }
    if (element.contextValue === "homeBranch" || element.contextValue === "pathBranch") {
      return this.listDir(dir);
    }
    return this.listCollectionAware(dir, path.basename(dir));
  }
}
