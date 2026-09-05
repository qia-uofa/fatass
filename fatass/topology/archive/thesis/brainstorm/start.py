import datetime

import fatass
from fatass.topology.archive.thesis.brainstorm import Brainstorm as Brainstorm


def start():
    node = Brainstorm()
    conversation_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = node._assets_dir() / f"{conversation_id}.md"
    print(f"starting conversation {conversation_id}, logging to {log_path.name}")

    fatass.free(
        readable=[],
        silent=False,
        permission_mode="acceptEdits",
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep",
        prompt=(
            f"Have a free-form brainstorming conversation with the user. "
            f"Log the conversation to `{log_path}` as you go: after every "
            f"user message and every one of your own replies, append a new "
            f"section to that file recording it (create the file with a "
            f"top-level heading naming the conversation id `{conversation_id}` "
            f"if it doesn't exist yet, then append '## User' or '## Agent' "
            f"subsections with the message text below each, in order, as the "
            f"conversation proceeds). Do this after every single turn, not "
            f"just at the end."
        ),
    )
