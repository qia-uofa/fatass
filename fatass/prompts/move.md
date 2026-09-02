You are reviewing a node's own directory right after `fatass move` renamed
its leaf segment (e.g. "a.old" -> "a.new") — a real content file, not a
new one. The mechanical part of the rename is already done: the class
definition, `__init__.py`'s import, and every same-directory transform's
own self-import of the class. Don't redo any of that, and don't touch
anything unrelated to the rename.

Your job is the part a text substitution can't do: read every `.py` file
in the current directory (the node's own class file and each transform)
and look for anything that still reads as the *old* name in a way only
understanding the code or prose reveals —

- a local variable, parameter, or loop name derived from the old stem
  (e.g. `old_stem_result = ...`)
- a mention of the old name inside a `fatass.free(...)` prompt string —
  these are read by an agent as instructions, so a stale name there is
  actively misleading, not just cosmetic
- a comment or docstring referring to the node by its old name
- an f-string or literal that spells out the old name for a human reader
  (a label, a log line, a written-out file name)

Fix what you find so it consistently reads as the new name. If a file has
none of these, leave it alone — this is a targeted cleanup pass, not a
rewrite.
