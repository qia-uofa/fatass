from pathlib import Path

_QUOTES = ("'", '"')


def read(path: Path) -> dict[str, str]:
    """Parse a plain KEY=VALUE dotenv file. Blank lines and lines starting
    with '#' are ignored; a value wrapped in matching quotes has them
    stripped. Missing file -> {}."""
    if not path.is_file():
        return {}

    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in _QUOTES:
            value = value[1:-1]
        values[key] = value
    return values


def write_var(path: Path, key: str, value: str) -> None:
    """Set `key=value` in a dotenv file — replacing an existing line for
    that key in place, or appending a new one. Other lines (including
    comments) are left untouched. Creates the file (and its parent dir)
    if it doesn't exist yet."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    new_line = f"{key}={value}"

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.partition("=")[0].strip() == key:
            lines[i] = new_line
            break
    else:
        lines.append(new_line)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
