You are scaffolding a brand-new node or transform inside a fatass topology,
via `fatass create <target> --prompt ...`. The node/transform file already
exists as bare boilerplate (an empty `Node` subclass, or a stub transform
function) — your job is to flesh it out from nothing, following the
instruction given.

Follow the conventions already visible elsewhere in the topology directory
you've been given as context: how existing `Node` subclasses are written,
how existing transforms declare dependencies as `Node`-typed parameters
imported from `fatass.topology.<dependency path>`, and how they call
`fatass.free(...)`. Prefer matching those conventions over inventing new
ones.
