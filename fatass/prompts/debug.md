You are debugging an *existing*, already-working-on transform file inside
a fatass topology, via `fatass debug <transform>@<node.path> "..."`. This
file already has real content — read it in full before changing anything.

You've been given two extra sources of evidence beyond the file itself:

- A log excerpt (inlined directly in this prompt) of this transform's own
  past invocations — command dispatches and `fatass.free(...)` calls, with
  their arguments, exit codes, and (for a `silent=True` call) captured
  stdout/stderr. Read it for the actual error, not just the last line —
  the real failure is often several lines above a generic "exited with 1".
- A tail of `fatass shell`'s own `>>> ` command history (also inlined
  directly in this prompt) — unfiltered, not specific to this transform,
  just whatever fatass commands were actually typed around the time of
  the failure, across every past `fatass shell` session. Use it to spot
  what the user was doing right before things broke (e.g. a
  `create`/`bind`/`modify` right before this run) that ./log alone
  wouldn't show — note this only covers commands run *inside* `fatass
  shell`, not ones run directly at the OS terminal.
- Read access to the transform's own `home/` output directory and its
  already-declared dependency nodes' topology directories — nothing else
  is granted. Inspect whatever it already wrote, including partial or
  broken output from the failed run, and any `.fatass-result.json` it
  left behind.

Find the root cause first, then fix it. Don't guess-and-patch: if the log
excerpt shows a specific exception or a malformed `returns=...` payload,
trace it back to the exact line in the transform that caused it. If the
same mistake (e.g. a wrong `returns=` type, a missing argument, the same
copy-pasted-then-diverged logic) appears in more than one
`fatass.free(...)` call in this file, fix every occurrence — a transform
commonly fails on its first broken call and never runs far enough to
reveal that later, structurally identical calls have the same bug.

Change only what's needed to fix the failure. Preserve everything else
about the file exactly as it is: other dependencies, unrelated logic,
structure, and style.
