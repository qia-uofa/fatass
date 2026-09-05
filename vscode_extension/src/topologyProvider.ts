import * as path from "path";
import * as vscode from "vscode";
import { execFileSync } from "child_process";
import { topologyDir } from "./workspaceRoot";

interface DependencySummary {
  path: string;
  class_name: string;
  children: string[];
}

interface TransformInfo {
  name: string;
  dependencies: DependencySummary[];
}

interface NodeSummary {
  path: string;
  /** fatass base class (Node/Chain/Single/Array). */
  class_name: string;
  /** The node's own declared class, e.g. "MyNode" -- what the tree
   * actually labels the node with, not its snake_case module/path name. */
  own_class_name: string;
  children: string[];
  transforms: TransformInfo[];
}

// Delegates to fatass's own `fatass.ls.list_node`/`list_root` (the same
// data `fatass ls` prints) rather than re-deriving a node's class and
// transform/dependency shape here -- that logic (importing the node,
// walking `discover()`, resolving each transform's Node-typed parameters)
// already exists and is nontrivial to duplicate correctly. Takes a whole
// batch of paths per process invocation -- `python` startup + importing
// `fatass` dominates the cost of a single call, so fetching one node at a
// time (one subprocess per tree row) made expanding a node with several
// children/transforms noticeably slow.
const LIST_NODES_SCRIPT = `
import sys, json, dataclasses
import fatass.ls as ls
from fatass.core.transform import _import_node

def summarize(path):
    if not path:
        return {
            "path": "",
            "class_name": "topology",
            "own_class_name": "topology",
            "children": ls.list_root(),
            "transforms": [],
        }
    data = dataclasses.asdict(ls.list_node(path))
    try:
        data["own_class_name"] = _import_node(path).__name__
    except Exception:
        data["own_class_name"] = path.split(".")[-1]
    return data

paths = json.loads(sys.argv[1])
print(json.dumps([summarize(p) for p in paths]))
`;

function fetchNodeSummaries(root: string, paths: string[]): NodeSummary[] {
  if (paths.length === 0) {
    return [];
  }
  try {
    const out = execFileSync("python", ["-c", LIST_NODES_SCRIPT, JSON.stringify(paths)], {
      cwd: root,
      encoding: "utf8",
    });
    return JSON.parse(out) as NodeSummary[];
  } catch {
    return paths.map((p) => ({
      path: p,
      class_name: "Node",
      own_class_name: p.split(".").pop() || "~",
      children: [],
      transforms: [],
    }));
  }
}

function childDotPath(parent: string, name: string): string {
  return parent ? `${parent}.${name}` : name;
}

function dirForDotPath(root: string, dotPath: string): string {
  return dotPath ? path.join(topologyDir(root), ...dotPath.split(".")) : topologyDir(root);
}

/** "MyNode" for a plain Node subclass, "MyNode(Chain)" when it's built on
 * a more specific fatass base class -- the base class name is only worth
 * showing when it adds information ("Node" is the assumed default). */
function classLabel(summary: NodeSummary): string {
  return summary.class_name === "Node" ? summary.own_class_name : `${summary.own_class_name}(${summary.class_name})`;
}

/** The dotted-path expression (see fatass's `..`-relative `cd` syntax in
 * CLAUDE.md) that reaches `target` from `owner` -- always starts with at
 * least one dot: N dots ascend N-1 levels from `owner`, then descend
 * straight into whatever of `target` remains below their common ancestor
 * (no separating dot between the dot-run and that remainder, matching
 * `node1..node2` for "node1's parent's child node2"). */
function relativeDotPath(owner: string, target: string): string {
  const ownerParts = owner ? owner.split(".") : [];
  const targetParts = target ? target.split(".") : [];
  let common = 0;
  while (common < ownerParts.length && common < targetParts.length && ownerParts[common] === targetParts[common]) {
    common++;
  }
  const ascend = ownerParts.length - common;
  return ".".repeat(ascend + 1) + targetParts.slice(common).join(".");
}

/** One node in the fatass topology tree (dotted path + real directory),
 * labeled with its actual declared class. */
export class NodeItem extends vscode.TreeItem {
  constructor(
    public readonly dotPath: string,
    public readonly dirPath: string,
    label: string,
    hasChildren: boolean
  ) {
    super(label, hasChildren ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None);
    this.contextValue = "node";
    this.tooltip = dotPath || "~";
    this.iconPath = new vscode.ThemeIcon("symbol-class");
  }
}

/** One transform belonging to a node, shown as a child of that node --
 * expands to the transform's declared Node-typed dependencies, which are
 * themselves NodeItems (so expanding one of those recurses into that
 * dependency's own subnodes and transforms, same as any other node). */
export class TransformItem extends vscode.TreeItem {
  constructor(
    public readonly ownerDotPath: string,
    name: string,
    public readonly dependencies: DependencySummary[]
  ) {
    super(
      name,
      dependencies.length > 0 ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None
    );
    this.contextValue = "transform";
    this.tooltip = `${name}@${ownerDotPath || "~"}`;
    this.iconPath = new vscode.ThemeIcon("symbol-method");
  }
}

export type TopologyElement = NodeItem | TransformItem;

export class TopologyProvider implements vscode.TreeDataProvider<TopologyElement> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<TopologyElement | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  // Keyed by dotPath. A child's full summary (including its own children
  // and transforms) is already known once its parent has been expanded,
  // so expanding it in turn is a cache hit rather than another subprocess
  // call -- cleared on refresh() since the underlying topology may have
  // changed.
  private readonly cache = new Map<string, NodeSummary>();

  constructor(private readonly root: string) {}

  refresh(): void {
    this.cache.clear();
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: TopologyElement): vscode.TreeItem {
    return element;
  }

  private fetchSummaries(paths: string[]): NodeSummary[] {
    const uncached = paths.filter((p) => !this.cache.has(p));
    if (uncached.length > 0) {
      for (const summary of fetchNodeSummaries(this.root, uncached)) {
        this.cache.set(summary.path, summary);
      }
    }
    return paths.map((p) => this.cache.get(p)!);
  }

  private nodeItem(summary: NodeSummary, label?: string): NodeItem {
    const hasChildren = summary.children.length > 0 || summary.transforms.length > 0;
    return new NodeItem(summary.path, dirForDotPath(this.root, summary.path), label ?? classLabel(summary), hasChildren);
  }

  getChildren(element?: TopologyElement): TopologyElement[] {
    if (!element) {
      const [rootSummary] = this.fetchSummaries([""]);
      return this.fetchSummaries(rootSummary.children).map((s) => this.nodeItem(s));
    }
    if (element instanceof TransformItem) {
      const ownerDotPath = element.ownerDotPath;
      return this.fetchSummaries(element.dependencies.map((d) => d.path)).map((s) =>
        this.nodeItem(s, relativeDotPath(ownerDotPath, s.path))
      );
    }
    const [summary] = this.fetchSummaries([element.dotPath]);
    const childPaths = summary.children.map((name) => childDotPath(element.dotPath, name));
    const subnodes = this.fetchSummaries(childPaths).map((s) => this.nodeItem(s));
    const transforms = summary.transforms.map((t) => new TransformItem(element.dotPath, t.name, t.dependencies));
    return [...subnodes, ...transforms];
  }

  /** A freshly-constructed NodeItem for `dotPath` ("" for the root),
   * without walking the tree from the top -- used to reveal a node whose
   * path is already known (e.g. "jump to this node" from the Node view)
   * rather than one the user actually expanded/clicked here. */
  nodeItemForPath(dotPath: string): NodeItem {
    const [summary] = this.fetchSummaries([dotPath]);
    return this.nodeItem(summary);
  }

  /** Required by `TreeView.reveal()` to expand/select an element that
   * wasn't reached by walking down from getChildren(undefined) -- vscode
   * needs to be able to climb back up to the root to know what to expand
   * along the way. A TransformItem's parent is the node it belongs to; a
   * NodeItem's parent is its inclusion parent (not whichever transform,
   * if any, was used to reach it). */
  getParent(element: TopologyElement): TopologyElement | undefined {
    if (element instanceof TransformItem) {
      return this.nodeItemForPath(element.ownerDotPath);
    }
    if (!element.dotPath) {
      return undefined;
    }
    const parts = element.dotPath.split(".");
    parts.pop();
    return this.nodeItemForPath(parts.join("."));
  }
}

const NODE_MIME_TYPE = "application/vnd.code.tree.fatasstopology";

/**
 * Drag-and-drop reparenting for the Topology view: dropping a node onto
 * another node (or onto the tree's own blank area, for the top level)
 * reparents it there via `fatass move`, keeping its own leaf name. Purely
 * a UI gesture over the same `moveNode` callback `extension.ts` already
 * wires the right-click "move..." command through -- this class only
 * decides *what* was dropped *where*, not how the actual move happens.
 * Only NodeItems (real nodes) can be dragged -- a TransformItem has
 * nothing to move.
 */
export class TopologyDragAndDropController implements vscode.TreeDragAndDropController<TopologyElement> {
  readonly dragMimeTypes = [NODE_MIME_TYPE];
  readonly dropMimeTypes = [NODE_MIME_TYPE];

  constructor(private readonly moveNode: (source: NodeItem, target: NodeItem | undefined) => void) {}

  handleDrag(source: readonly TopologyElement[], dataTransfer: vscode.DataTransfer): void {
    const nodes = source.filter((item): item is NodeItem => item instanceof NodeItem);
    dataTransfer.set(NODE_MIME_TYPE, new vscode.DataTransferItem(nodes));
  }

  handleDrop(target: TopologyElement | undefined, dataTransfer: vscode.DataTransfer): void {
    if (target instanceof TransformItem) {
      return;
    }
    const transferItem = dataTransfer.get(NODE_MIME_TYPE);
    if (!transferItem) {
      return;
    }
    const sources = transferItem.value as NodeItem[];
    for (const source of sources) {
      this.moveNode(source, target);
    }
  }
}
