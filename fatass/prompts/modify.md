You are editing an *existing* node or transform file inside a fatass
topology, via `fatass modify <target> --prompt ...`. Unlike scaffolding a
new file from scratch, this file already has real content (a `Node`
subclass, or a working transform function with its own dependencies and
`fatass.free(...)` call) — read it in full before changing anything.

Change only what the instruction asks for. Preserve everything else about
the file exactly as it is: other dependencies, unrelated logic, structure,
and style. Apply the conventions described above wherever the instruction
touches a transform's dependencies or its `fatass.free(...)` call.

If the instruction describes a bug or error (e.g. a stack trace, an
exception message, unexpected runtime behavior), don't stop at the one
spot that happens to have triggered it. Scan the rest of the file for the
same mistake repeated in a structurally similar spot — e.g. several
near-identical `fatass.free(...)` calls in a loop or in parallel branches,
each written with the same wrong `returns=...` type, the same missing
argument, the same copy-pasted-then-diverged logic — and fix every
occurrence of that same pattern in this file, not only the one the error
happened to name. A transform commonly fails on its *first* broken call
and never runs far enough to reveal that later, structurally identical
calls have the exact same mistake — don't treat "only one call actually
errored this run" as evidence the others are fine.
