import fatass
from fatass.topology.thesis.brainstorm import Brainstorm as Brainstorm
from fatass.topology.thesis.examples import Examples as Examples


def search(brainstorm: Brainstorm):
    node = Examples()
    out_dir = node._assets_dir()

    print("search: extracting student profile from brainstorm dialogues")
    profile = fatass.free(
        readable=[brainstorm],
        returns=dict,
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        tools="Read,Write,Glob,Grep",
        prompt=(
            "brainstorm depends on node `thesis.brainstorm` — its readable "
            "directory holds one or more `<conversation-id>.md` files (e.g. "
            "`20260826-113000.md`), each logging a free-form brainstorming "
            "dialogue between the user and an agent as alternating "
            "'## User' / '## Agent' sections. Read all of these files in "
            "full. From the dialogue, extract the profile of the student "
            "who is writing the thesis: their country, university, "
            "degree/program (e.g. PhD, MSc), major/field of study, and "
            "thesis topic, plus anything else useful for finding "
            "comparable past theses (sub-field, methodology, keywords). "
            "Report your result as a JSON object with keys `country`, "
            "`university`, `program`, `major`, `topic`, and `keywords` (a "
            "list of strings) — use null for any field not mentioned in "
            "the dialogues, and add extra keys only if the dialogue "
            "reveals something specific and useful that doesn't fit those "
            "fields."
        ),
    )
    print(f"search: extracted profile: {profile}")

    print("search: searching the web for past theses matching this profile")
    fatass.free(
        readable=[],
        silent=False,
        permission_mode="bypassPermissions",
        model="sonnet",
        effort="high",
        tools="Read,Write,Edit,Glob,Grep,Bash,WebSearch,WebFetch",
        prompt=(
            "Here is the profile of a student writing a thesis, extracted "
            f"from their brainstorming dialogues:\n\n{profile}\n\n"
            "Search the internet for past theses (completed dissertations "
            "or theses) that plausibly match this profile — same or "
            "closely related university/country when possible, the same "
            "major or field of study, and a similar or related topic. "
            "Prioritize theses that are actually downloadable (an "
            "open-access university repository, ProQuest open access, "
            "arXiv, or a publicly posted PDF) over ones that are merely "
            "referenced elsewhere. For each matching thesis you find, "
            f"download its PDF into `{out_dir}` using a descriptive "
            "filename (e.g. `<author>_<short-title>.pdf`); if no PDF is "
            "available for a match, save its abstract/full text there "
            "instead as a markdown file with the same naming style. Aim "
            "for a handful of the best matches rather than an exhaustive "
            "list — quality of match over quantity."
        ),
    )
    print("search: done")
