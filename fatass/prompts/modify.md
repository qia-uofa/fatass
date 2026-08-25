You are editing an *existing* node or transform file inside a fatass
topology, via `fatass modify <target> --prompt ...`. Unlike scaffolding a
new file from scratch, this file already has real content (a `Node`
subclass, or a working transform function with its own dependencies and
`fatass.free(...)` call) — read it in full before changing anything.

Change only what the instruction asks for. Preserve everything else about
the file exactly as it is: other dependencies, unrelated logic, structure,
and style. Apply the conventions described above wherever the instruction
touches a transform's dependencies or its `fatass.free(...)` call.
