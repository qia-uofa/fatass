import fatass


def build():
    fatass.free(
        silent=True,
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep",
        readable=[],
        prompt=(
            "Write a short, self-contained roster entry to `entry.md` in "
            "the current directory: an invented person's name, role, and "
            "one-sentence fun fact. Keep it to three lines total."
        ),
    )
