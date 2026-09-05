# fatass-vscode

VSCode extension for browsing and operating on a fatass topology.

## Features (see `hi.md`)

- Activates automatically when a workspace contains `fatass/topology/`.
- **Topology** view: tree of nodes (dotted-path addressed, mirroring `fatass ls -r`),
  built by walking `fatass/topology/` for directories containing `<name>.py`.
- **Node Content** view: shows the selected node's files, toggling (via the
  swap button in the view title) between its `home/` assets and its
  `fatass/topology/` class file directory.
- Right-click context menu on a topology node: `cd`, `run`, `build`, `modify`,
  `create`, `move`, `copy`, `remove`, `purge`, `vim` — each shells out to
  `python -m fatass ...` in a shared integrated terminal, so normal terminal
  output/approval applies.

## Build

```
npm install
npm run compile
```

Then run the "Extension" launch config (F5) from a VSCode window opened on
this `vscode_plugin/` folder, or `vsce package` to produce a `.vsix`.

Not yet verified against a real VSCode host in this environment (no
node/npm available here) — build and smoke-test before relying on it.
