def pascal_case(snake: str) -> str:
    """`"writing_sample"` -> `"WritingSample"` — the conventional class name
    for a node whose own file/directory is named `snake` (its last dotted
    topology-path segment)."""
    return "".join(word.capitalize() for word in snake.split("_"))
