from pathlib import Path

import fatass
from fatass.topology.examples.portfolio import Portfolio as Portfolio
from fatass.core.transform import _import_node
from fatass.topology.examples.portfolio.cv.checkpoints import Checkpoints as Checkpoints
from fatass.topology.examples.portfolio.cv.draft import Draft as Draft
from fatass.topology.examples.portfolio.cv.templates import Templates as Templates
from fatass.topology.examples.portfolio.projects import Projects as Projects
from fatass.topology.examples.portfolio.profile.basic_info.basic_info import BasicInfo
from fatass.topology.examples.portfolio.profile.photo.photo import Photo
from fatass.topology.examples.portfolio.profile.summary.summary import Summary
from fatass.topology.examples.portfolio.profile.skills.skills import Skills
from fatass.topology.examples.portfolio.profile.interests.interests import Interests
from fatass.topology.examples.portfolio.profile.education.education import Education
from fatass.topology.examples.portfolio.profile.working_experience.working_experience import WorkingExperience
from fatass.topology.examples.portfolio.profile.research_experience.research_experience import ResearchExperience
from fatass.topology.examples.portfolio.profile.certifications.certifications import Certifications
from fatass.topology.examples.portfolio.profile.languages.languages import Languages
from fatass.topology.examples.portfolio.profile.awards.awards import Awards
from fatass.topology.examples.portfolio.profile.publications.publications import Publications


def _is_real_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _single_populated(cls) -> bool:
    try:
        return _is_real_file(cls._file_path())
    except Exception:
        return False


def _tuple_populated(cls) -> bool:
    try:
        return any(_is_real_file(cls._file_path(f)) for f in cls.FIELDS)
    except Exception:
        return False


_SINGLE_MDS = (("Summary", Summary), ("Skills", Skills), ("Interests", Interests))
_CHAINS = (
    ("Education", Education),
    ("Work experience", WorkingExperience),
    ("Research experience", ResearchExperience),
    ("Certifications", Certifications),
    ("Languages", Languages),
    ("Awards", Awards),
    ("Publications", Publications),
)


def _report_state() -> None:
    print()
    print("=" * 60)
    print("Portfolio state")
    print("=" * 60)
    print(f"Checkpoints (saved CV PDFs): {Checkpoints.length()}")
    print(f"Templates:                   {Templates.length()}")
    print(f"Projects:                    {Projects.length()}")
    draft_pdf = Draft._assets_dir() / "main.pdf"
    print(f"Draft built:                 {'yes' if _is_real_file(draft_pdf) else 'no'}  ({draft_pdf})")
    print()
    print("Profile:")
    print(f"  basic_info: {'filled in' if _tuple_populated(BasicInfo) else 'empty'}")
    print(f"  photo:      {'set' if _single_populated(Photo) else 'not set'}")
    for label, cls in _SINGLE_MDS:
        print(f"  {label}: {'written' if _single_populated(cls) else 'empty'}")
    for label, cls in _CHAINS:
        n = cls.length()
        print(f"  {label}: {n} entr{'y' if n == 1 else 'ies'}")
    print("=" * 60)


def _add_checkpoint() -> None:
    raw = input("Path to an existing PDF to add as a checkpoint (blank to cancel): ").strip().strip('"')
    if not raw:
        print("cancelled")
        return
    src = Path(raw).expanduser()
    if not src.is_file():
        print(f"error: {src} is not a file")
        return
    Checkpoints.extend()
    index = Checkpoints.length() - 1
    item = Checkpoints()[index]
    item.file.write_bytes(src.read_bytes())
    print(f"added checkpoints[{index}] from {src}")


def _extract_from_checkpoint() -> None:
    if Checkpoints.length() == 0:
        print("no checkpoints yet — add one first")
        return
    print("extracting profile info from the newest checkpoint...")
    fatass.run_transform("portfolio.profile", "fetch", force=True)
    print("extracting project info from the newest checkpoint...")
    fatass.run_transform("portfolio.projects", "fetch", force=True)
    print("done")


def _manage_assets() -> None:
    while True:
        print()
        print("Manage assets:")
        print("  1. List files under a node")
        print("  2. Purge a node's own assets")
        print("  3. Back")
        choice = input("> ").strip()
        if choice == "3" or not choice:
            return
        node_path = input("node path, e.g. \"profile.summary\" (blank to cancel): ").strip()
        if not node_path:
            print("cancelled")
            continue
        full_path = f"portfolio.{node_path}"
        try:
            node_cls = _import_node(full_path)
        except Exception as exc:
            print(f"error: {exc}")
            continue
        if choice == "1":
            assets_dir = node_cls._assets_dir()
            files = [p for p in assets_dir.rglob("*") if p.is_file()]
            if not files:
                print(f"(no files under {assets_dir})")
                continue
            for p in sorted(files):
                print(f"  {p.relative_to(assets_dir)}  ({p.stat().st_size} bytes)")
        elif choice == "2":
            confirm = input(f"really delete all of {full_path}'s own content? [y/N] ").strip().lower()
            if confirm != "y":
                print("cancelled")
                continue
            count = fatass.purge_node(full_path)
            print(f"purged: {count}")
        else:
            print("unknown option")


_MENU = """
What would you like to do?
  1. Add an existing PDF to checkpoints
  2. Extract info from the newest checkpoint (profile + projects)
  3. Manage assets (list/purge a node's files)
  4. Re-show portfolio state
  5. Exit
"""


def main(portfolio: Portfolio):
    _report_state()
    while True:
        print(_MENU)
        choice = input("> ").strip()
        if choice == "1":
            _add_checkpoint()
        elif choice == "2":
            _extract_from_checkpoint()
        elif choice == "3":
            _manage_assets()
        elif choice == "4":
            _report_state()
        elif choice == "5" or choice.lower() in ("exit", "quit", "q"):
            print("bye")
            return
        else:
            print("unknown option — pick a number from the menu")
