import fatass
from fatass.topology.examples.portfolio.cv.checkpoints import Checkpoints as Checkpoint
from fatass.topology.examples.portfolio.cv.checkpoints.file import File as File
from fatass.topology.examples.portfolio.profile.basic_info.basic_info import BasicInfo
from fatass.topology.examples.portfolio.profile.summary.summary import Summary
from fatass.topology.examples.portfolio.profile.education.education import Education
from fatass.topology.examples.portfolio.profile.education.entry.entry import Entry as EducationEntry
from fatass.topology.examples.portfolio.profile.working_experience.working_experience import WorkingExperience
from fatass.topology.examples.portfolio.profile.working_experience.entry.entry import Entry as WorkingExperienceEntry
from fatass.topology.examples.portfolio.profile.research_experience.research_experience import ResearchExperience
from fatass.topology.examples.portfolio.profile.research_experience.entry.entry import Entry as ResearchExperienceEntry
from fatass.topology.examples.portfolio.profile.skills.skills import Skills
from fatass.topology.examples.portfolio.profile.certifications.certifications import Certifications
from fatass.topology.examples.portfolio.profile.certifications.entry.entry import Entry as CertificationsEntry
from fatass.topology.examples.portfolio.profile.languages.languages import Languages
from fatass.topology.examples.portfolio.profile.languages.entry.entry import Entry as LanguagesEntry
from fatass.topology.examples.portfolio.profile.awards.awards import Awards
from fatass.topology.examples.portfolio.profile.awards.entry.entry import Entry as AwardsEntry
from fatass.topology.examples.portfolio.profile.publications.publications import Publications
from fatass.topology.examples.portfolio.profile.publications.entry.entry import Entry as PublicationsEntry
from fatass.topology.examples.portfolio.profile.interests.interests import Interests

_CHAINS = (
    (
        "education", Education, EducationEntry,
        "a repeated section, one entry per degree/program",
        "One entry per degree or diploma program (not short courses or "
        "certifications -- those go under `certifications`). `honors` covers "
        "things like cum laude, dean's list, or a distinction awarded as part "
        "of the degree itself, not standalone prizes (those go under "
        "`awards`). If end_time is missing/blank/\"present\", the program is "
        "still ongoing.",
    ),
    (
        "working_experience", WorkingExperience, WorkingExperienceEntry,
        "a repeated section, one entry per job",
        "One entry per paid job, internship, or industry/non-research "
        "position with an employer -- roles whose primary purpose was "
        "producing work product or a service, not conducting research. If a "
        "listed role's main activity was research (e.g. research assistant, "
        "research intern, lab work, thesis-adjacent work under a supervisor "
        "or PI), put it under `research_experience` instead, even if it was "
        "paid. When a single item is ambiguous, prefer `research_experience` "
        "if it mentions an advisor, lab, PI, or academic institution, and "
        "`working_experience` if it mentions a company, product, or client.",
    ),
    (
        "research_experience", ResearchExperience, ResearchExperienceEntry,
        "a repeated section, one entry per research position/project",
        "One entry per research position, research assistantship, thesis, "
        "or research-focused project done under an advisor/PI or as part of "
        "a lab/institution -- not a course project or industry job. `lab` is "
        "the lab/group name if one is given (empty string if none). "
        "`advisor` is the supervising professor/PI's name (empty string if "
        "none named). `institution` is the university/organization hosting "
        "the research. `role` is the position title (e.g. \"Research "
        "Assistant\", \"Undergraduate Researcher\", \"Bachelor Thesis "
        "Student\"). `description` should mention the research topic and any "
        "concrete outcome (paper, tool, result).",
    ),
    (
        "certifications", Certifications, CertificationsEntry,
        "a repeated section, one entry per certification",
        "One entry per formal certification, license, or short professional "
        "course with a credential/certificate issued by a named body (e.g. "
        "a cloud provider, a MOOC platform, a professional association) -- "
        "not a full degree program (that goes under `education`) and not a "
        "competition prize (that goes under `awards`).",
    ),
    (
        "languages", Languages, LanguagesEntry,
        "a repeated section, one entry per language spoken",
        "One entry per spoken/written language, including the native "
        "language if stated. Normalize `proficiency` to whatever scale the "
        "CV uses (e.g. CEFR A1-C2, \"native\", \"fluent\", \"conversational\", "
        "\"basic\") -- copy the CV's own wording rather than inventing a "
        "level it doesn't state.",
    ),
    (
        "awards", Awards, AwardsEntry,
        "a repeated section, one entry per award",
        "One entry per standalone prize, scholarship, honor, or competition "
        "placement that was awarded to the person by name -- not a degree "
        "honor folded into an education entry (that stays in `education`'s "
        "`honors` field) and not a certification.",
    ),
    (
        "publications", Publications, PublicationsEntry,
        "a repeated section, one entry per publication",
        "One entry per paper, preprint, poster, or other published/"
        "submitted written research output. `authors` should list all "
        "authors as given (comma-separated), in their original order. "
        "`venue` is the journal/conference/workshop name, or \"preprint\" / "
        "the hosting server (e.g. arXiv) if unpublished. Do not include "
        "talks or presentations with no associated written output here.",
    ),
)
_SINGLE_MDS = (
    (
        "summary", Summary, "a short professional summary, in markdown",
        "A short (2-5 sentence) first- or third-person professional summary "
        "or objective statement, paraphrased from whatever framing text the "
        "CV opens with. If the CV has no explicit summary/objective section, "
        "write a brief one from the overall content instead of leaving it "
        "empty.",
    ),
    (
        "skills", Skills, "a list of skills, in markdown",
        "A markdown bullet or grouped list of skills (e.g. programming "
        "languages, tools, frameworks, spoken languages if the CV mixes "
        "them in here rather than in a separate languages section). "
        "Preserve any grouping/categories the CV uses (e.g. bold category "
        "labels followed by a comma-separated list).",
    ),
    (
        "interests", Interests, "a short list/paragraph of interests, in markdown",
        "A short list or paragraph of research interests, hobbies, or "
        "personal interests, whichever the CV includes. Use \"\" if the CV "
        "genuinely has no such section -- do not invent interests.",
    ),
)


def _tuple_fields_str(fields: tuple[str, ...]) -> str:
    return ", ".join(f'"{f}": str' for f in fields)


def _build_prompt() -> str:
    lines = [
        "Dependency `pdf` (node `cv.checkpoint`, the newest (last) entry's "
        "`file`, a `File` "
        "node) has a readable directory containing exactly one file, `_.pdf` — "
        "the user's old CV. Read it (use Bash to extract text if the Read tool "
        "reports it as unreadable/password-protected) and extract every piece "
        "of profile information it contains into a single JSON object with "
        "exactly this shape:",
        "",
        "{",
        f'  "basic_info": {{{_tuple_fields_str(BasicInfo.FIELDS)}}},',
    ]
    for key, single_cls, note, _guidance in _SINGLE_MDS:
        lines.append(f'  "{key}": str,  // {note}')
    for key, chain_cls, entry_cls, note, _guidance in _CHAINS:
        entry_fields = _tuple_fields_str(entry_cls.FIELDS)
        lines.append(f'  "{key}": [{{{entry_fields}}}, ...],  // {note}')
    lines += [
        "}",
        "",
        "Use \"\" for any field the CV doesn't mention, and [] for any list "
        "section the CV doesn't have. Every key above must be present.",
        "",
        "Section-by-section guidance (read carefully -- some sections overlap "
        "and need to be told apart correctly):",
        "",
    ]
    for key, _single_cls, _note, guidance in _SINGLE_MDS:
        lines.append(f"- `{key}`: {guidance}")
    for key, _chain_cls, _entry_cls, _note, guidance in _CHAINS:
        lines.append(f"- `{key}`: {guidance}")
    return "\n".join(lines)


def fetch(checkpoint: Checkpoint):
    print("fetch: extracting profile data from old CV")
    pdf: File = checkpoint[Checkpoint.length() - 1].file
    data = fatass.free(
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        tools="Read,Write,Bash",
        readable=[pdf],
        returns=dict,
        prompt=_build_prompt(),
    )

    basic_info = data.get("basic_info", {})
    for field in BasicInfo.FIELDS:
        BasicInfo.write(field, str(basic_info.get(field, "")))

    Summary.write(str(data.get("summary", "")))
    Skills.write(str(data.get("skills", "")))
    Interests.write(str(data.get("interests", "")))

    for key, chain_cls, _entry_cls, _note, _guidance in _CHAINS:
        _fill_chain(chain_cls, data.get(key, []))

    print("fetch: done")


def _fill_chain(chain_cls, items: list[dict]) -> None:
    while chain_cls.length() > 0:
        chain_cls.pop()
    chain = chain_cls()
    for item in items:
        chain_cls.extend()
        entry = chain[chain_cls.length() - 1].entry
        for field in entry.FIELDS:
            entry.write(field, str(item.get(field, "")))
