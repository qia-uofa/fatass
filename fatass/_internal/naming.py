import re


def pascal_case(snake: str) -> str:
    """`"writing_sample"` -> `"WritingSample"` — the conventional class name
    for a node whose own file/directory is named `snake` (its last dotted
    topology-path segment)."""
    return "".join(word.capitalize() for word in snake.split("_"))


def pascal_node_path(node_path: str) -> str:
    """"jrpg.design.overview" -> "Jrpg.Design.Overview" (and
    "items[0].room" -> "Items[0].Room") — the display form for a node
    path in any command's own success/status output, matching the
    enforced-PascalCase input convention (`pascal_case`, applied per
    dotted segment) — a "[idx]" chain-index suffix glued onto a segment
    is preserved as-is, not itself PascalCased."""
    segments = []
    for seg in node_path.split("."):
        name, bracket, index = seg.partition("[")
        segments.append(pascal_case(name) + bracket + index)
    return ".".join(segments)


def snake_case(pascal: str) -> str:
    """Inverse of `pascal_case` — exact for any name that function itself
    produced, e.g. `"WritingSample"` -> `"writing_sample"`. `pascal_case`
    always starts each word with exactly one uppercase letter followed
    only by lowercase letters/digits (`.capitalize()`), so an uppercase
    letter unambiguously marks a new word boundary here too — insert
    `"_"` before each one (except a leading one, which needs no
    separator) and lowercase everything. Used by `fatass touch` to turn
    a child's signature class name (e.g. "Topics", the shape `fatass.
    signature` itself renders a child's name in) back into the node-path
    segment (directory/file-name) that names it."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", pascal).lower()


_LEADING_UNDERSCORES = re.compile(r"^_+")
_TRAILING_UNDERSCORES = re.compile(r"_+$")
_UPPER_WORD = re.compile(r"[A-Z][a-z]*[0-9]*")
_LOWER_WORD = re.compile(r"[a-z]+[0-9]*")
_DIGIT_RUN = re.compile(r"[0-9]+")

_SYMBOL_NAMES = {
    "-": "dash", ".": "dot", ",": "comma", "&": "and", "+": "plus",
    "%": "percent", "'": "apostrophe", "~": "tilde", "@": "at",
    "#": "hash", "!": "bang", "(": "lparen", ")": "rparen",
    "[": "lbracket", "]": "rbracket", "=": "equals", ";": "semicolon",
    ":": "colon", "$": "dollar",
}
"""Short, hand-picked names for common ASCII punctuation, used by
`escape_snake_case` so a symbol character can still contribute a valid
identifier chunk (`"my-folder"` -> `"my_escdash_folder"`, not a literal,
illegal `-` embedded in the result). A character missing from this table
falls back to its hex codepoint (`f"u{ord(ch):x}"`) instead of crashing —
readable for common punctuation, always safe for anything else."""


def _tokenize_arbitrary_name(core: str) -> list[str]:
    """Scans `core` (a name with no leading/trailing underscore run — see
    `escape_snake_case`, which strips those first) left to right, greedily
    matching one of four token kinds at each position, in priority order:

    1. `[A-Z][a-z]*[0-9]*` — a single capital letter, its lowercase tail
       (if any), and any trailing digits — one word. A single capital
       (not `[A-Z]+`) so a run of capitals becomes that many one-letter
       words instead of one merged blob — reassembling them (`pascal_
       case`, itself just "capitalize each word") naturally reproduces
       the original acronym intact, e.g. "XMLParser" -> ["x","m","l",
       "parser"] -> "XMLParser", not the wrong "Xmlparser".
    2. `[a-z]+[0-9]*` — an all-lowercase run (plus trailing digits) not
       already claimed by (1).
    3. `[0-9]+` — a digit run with no letters in front of it at all
       (already-consumed trailing digits after (1)/(2) never reach this)
       — escaped as `"esc" + digits` since an identifier chunk can't
       start with a digit on its own.
    4. Anything else — one character at a time — escaped as `"esc" +`
       its name in `_SYMBOL_NAMES` (or a hex-codepoint fallback).

    A space or underscore is a plain separator: skipped, contributing no
    token of its own (mid-string underscores reach here only because
    `escape_snake_case` already peeled off the leading/trailing run
    before calling this). Scanning is a plain sequential loop — not
    `re.finditer` — specifically so a token can start immediately after
    ANY previous token (a digit run, a symbol escape, ...) without
    needing a lookbehind for "preceded by a separator": every position
    this loop tries IS already "right after whatever came before"."""
    words: list[str] = []
    pos, length = 0, len(core)
    while pos < length:
        ch = core[pos]
        if ch in " _":
            pos += 1
            continue
        match = _UPPER_WORD.match(core, pos)
        if match:
            words.append(match.group().lower())
            pos = match.end()
            continue
        match = _LOWER_WORD.match(core, pos)
        if match:
            words.append(match.group())
            pos = match.end()
            continue
        match = _DIGIT_RUN.match(core, pos)
        if match:
            words.append("esc" + match.group())
            pos = match.end()
            continue
        words.append("esc" + _SYMBOL_NAMES.get(ch, f"u{ord(ch):x}"))
        pos += 1
    return words


def escape_snake_case(name: str) -> str:
    """Converts an arbitrary string — e.g. a real filesystem directory
    name being mirrored by `fatass.node.dir.Dir._mirror_subdirs`, which
    isn't guaranteed to already be a valid Python identifier the way
    `snake_case`'s own input always is — into a valid snake_case node
    name, never losing information (two different inputs never collide
    on the same output) and always round-tripping cleanly through
    `pascal_case` for the matching class name.

    A leading and/or trailing run of underscores is pulled off first and
    re-encoded as its own `f"escuds{count}"` word (e.g. `"_private"` ->
    `"escuds1_private"`, `"__dunder__"` -> `"escuds2_dunder_escuds2"`) —
    preserving exactly how many there were, at which end, rather than
    collapsing them into ordinary word-separators like a mid-string
    underscore. What's left (`_tokenize_arbitrary_name`) is split into
    words on capital letters, lowercase runs, digit runs, and escaped
    symbols, each joined back with `"_"` — e.g. `"MyCoolFolder"` ->
    `"my_cool_folder"`, `"123folder"` -> `"esc123_folder"`, `"my-folder"`
    -> `"my_escdash_folder"`. `pascal_case(escape_snake_case(name))`
    gives the matching PascalCase class name for free — no separate
    "arbitrary to Pascal" function needed, since `pascal_case` already
    does exactly "capitalize each underscore-separated word"."""
    leading = _LEADING_UNDERSCORES.match(name)
    leading_n = len(leading.group()) if leading else 0
    core = name[leading_n:] if leading_n else name
    trailing = _TRAILING_UNDERSCORES.search(core)
    trailing_m = len(trailing.group()) if trailing else 0
    if trailing_m:
        core = core[: len(core) - trailing_m]

    words = _tokenize_arbitrary_name(core)
    if leading_n:
        words = [f"escuds{leading_n}"] + words
    if trailing_m:
        words = words + [f"escuds{trailing_m}"]
    return "_".join(words)
