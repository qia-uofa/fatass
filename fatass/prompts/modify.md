You are editing an *existing* node or transform file inside a fatass
topology, via `fatass modify <target> --prompt ...`. Unlike scaffolding a
new file from scratch, this file already has real content (a `Node`
subclass, or a working transform function with its own dependencies and
`fatass.free(...)` calls) — read it in full before changing anything.

Change only what the instruction asks for. Preserve everything else about
the file exactly as it is: other dependencies, unrelated logic, structure,
and style. If the instruction is about a transform's dependencies, keep
using the established convention of `Node`-typed parameters imported from
`fatass.topology.<dependency path>`.
