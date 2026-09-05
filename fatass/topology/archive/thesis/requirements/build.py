import fatass
from fatass.topology.archive.thesis.brainstorm import Brainstorm as Brainstorm
from fatass.topology.archive.thesis.requirements import Requirements as Requirements


def build(brainstorm: Brainstorm):
    print("build: reading brainstorm chat history and researching bachelor thesis requirements")
    requirements = fatass.free(
        readable=[brainstorm],
        returns=str,
        silent=True,
        permission_mode="bypassPermissions",
        model="opus",
        effort="high",
        tools="Read,Write,Edit,Glob,Grep,WebSearch,WebFetch",
        prompt="""
Node `thesis.brainstorm` is a dependency — read its readable directory in
full (the chat history / notes it contains) to understand the specific
thesis topic, program, institution, and any constraints already discussed.

Using that context, use web search to research the actual, current
requirements for submitting a bachelor's thesis in this program/
institution (or, if the institution isn't identifiable from the
brainstorm content, the general/typical requirements for a bachelor
thesis submission) and compose a hyperdetailed requirements document
covering the entire process end-to-end, from starting to write the
thesis through actually obtaining the credits for it. Cover, at minimum:

- Eligibility/prerequisites to start (credits completed, supervisor
  assignment/approval, proposal or exposé submission and approval)
- Formal registration/enrollment steps and deadlines for the thesis
- Topic approval process and any required forms
- Writing phase: allowed duration, extensions, supervision meeting
  expectations, progress check-ins if any
- Formatting requirements: length, structure, citation style, language,
  required sections (abstract, declaration of authorship/originality,
  etc.)
- Submission process: format (digital/print/both), number of copies,
  submission deadline mechanics, plagiarism/originality checks
- Grading process: who grades, first/second reviewer, grading criteria,
  timeline for receiving a grade
- Defense/colloquium/presentation requirements if applicable
- Steps after grading to have the credits actually posted/recognized
  (registrar processes, ECTS transfer, graduation requirements tie-in)
- Any relevant deadlines, forms, or offices/contacts involved at each step

Cite where each piece of information came from (web sources) so it can be
verified later. Write the finished document directly as your reported
result — do not write the output file yourself, the caller writes it.
""",
    )
    (Requirements()._assets_dir() / "_.md").write_text(requirements, encoding="utf-8")
