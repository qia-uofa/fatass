import csv
import importlib.util
import io
import shutil
import subprocess
import unicodedata

import fatass
from fatass.core.transform import _import_node

from fatass.topology.examples.portfolio.profile import Profile as Profile
from fatass.topology.examples.portfolio.projects import Projects as Projects
from fatass.topology.examples.portfolio.cv.templates import Templates as Templates
from fatass.topology.examples.portfolio.cv.draft import Draft as Draft

_GENERATOR = "build_cv.py"

# pdflatex's default font encoding can't render some Unicode characters that
# show up in freely-generated summary text (e.g. a real minus sign rather
# than a hyphen); replace them with ASCII equivalents before compiling.
_UNICODE_TEX_REPLACEMENTS = {
    "−": "-",  # MINUS SIGN
}
# Greek letters (lowercase U+03B1-U+03C9, uppercase equivalents) map to their
# LaTeX math macros since freely-generated text sometimes uses them as symbols
# (e.g. lambda calculus).
_GREEK_CODEPOINTS = {
    "alpha": 0x03B1, "beta": 0x03B2, "gamma": 0x03B3, "delta": 0x03B4,
    "epsilon": 0x03B5, "zeta": 0x03B6, "eta": 0x03B7, "theta": 0x03B8,
    "iota": 0x03B9, "kappa": 0x03BA, "lambda": 0x03BB, "mu": 0x03BC,
    "nu": 0x03BD, "xi": 0x03BE, "pi": 0x03C0, "rho": 0x03C1,
    "sigma": 0x03C3, "tau": 0x03C4, "upsilon": 0x03C5, "phi": 0x03C6,
    "chi": 0x03C7, "psi": 0x03C8, "omega": 0x03C9,
}
for _name, _codepoint in _GREEK_CODEPOINTS.items():
    _UNICODE_TEX_REPLACEMENTS[chr(_codepoint)] = f"$\\{_name}$"
    _UNICODE_TEX_REPLACEMENTS[chr(_codepoint).upper()] = f"$\\{_name.capitalize()}$"
del _name, _codepoint, _GREEK_CODEPOINTS
# Blackboard-bold letters (double-struck capitals, U+2102/U+210D/U+2115/U+2119/
# U+211A/U+211D/U+2124) map to their LaTeX \mathbb macros since freely-generated
# text sometimes uses them for number sets (e.g. "subsets of R^2" written as R).
_BLACKBOARD_BOLD = {
    "C": 0x2102, "H": 0x210D, "N": 0x2115, "P": 0x2119,
    "Q": 0x211A, "R": 0x211D, "Z": 0x2124,
}
for _letter, _codepoint in _BLACKBOARD_BOLD.items():
    # \mathbb needs amssymb/amsfonts, which templates don't necessarily load;
    # \mathbf is core LaTeX math and always available.
    _UNICODE_TEX_REPLACEMENTS[chr(_codepoint)] = f"$\\mathbf{{{_letter}}}$"
del _letter, _codepoint, _BLACKBOARD_BOLD


def _sanitize_tex(tex: str) -> str:
    for char, replacement in _UNICODE_TEX_REPLACEMENTS.items():
        tex = tex.replace(char, replacement)
    # Catch-all: pdflatex's default font encoding can't render arbitrary
    # Unicode, and freely-generated text can contain any symbol beyond what
    # the explicit table above anticipates. Strip accents/diacritics down to
    # their ASCII base letter, and drop anything else non-ASCII outright,
    # rather than let an unanticipated character fail the whole compile.
    normalized = unicodedata.normalize("NFKD", tex)
    return "".join(c for c in normalized if not unicodedata.combining(c) and ord(c) < 128)


# ---------------------------------------------------------------------------
# generate_tex() (the generator script copied in from templates[i]) expects
# each dependency to expose a small "read" API (`.read()` / `.read(field)` /
# `.length()` / `[i]` / attribute access to schema children) that plain
# fatass Node/Tuple/Single/Chain classes don't actually provide (those only
# expose `write()`/`_file_path()`/`_assets_dir()`). These thin views adapt
# the real classes to that expected API without touching the generator
# script itself.
# ---------------------------------------------------------------------------

class _TupleView:
    def __init__(self, cls):
        self._cls = cls

    def read(self, field):
        path = self._cls._file_path(field)
        return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


class _SingleView:
    def __init__(self, cls):
        self._cls = cls

    def read(self):
        path = self._cls._file_path()
        return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


class _CsvView:
    def __init__(self, cls):
        self._cls = cls

    def read(self):
        path = self._cls._file_path()
        if not path.is_file():
            return []
        return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


_IMAGE_SINGLE_CLASSES = tuple(
    cls for cls in (getattr(fatass, "SinglePng", None), getattr(fatass, "SingleJpg", None))
    if cls is not None
)


class _ImageView:
    """A binary Single (SinglePng/SingleJpg — e.g. Profile.photo) has no
    sensible `.read()` as text; a template needs its file path instead,
    to hand straight to `\\includegraphics`."""

    def __init__(self, cls):
        self._cls = cls

    def path(self):
        p = self._cls._file_path()
        return str(p) if p.is_file() and p.stat().st_size > 0 else None


def _view_for(cls):
    if issubclass(cls, fatass.SingleCsv):
        return _CsvView(cls)
    if _IMAGE_SINGLE_CLASSES and issubclass(cls, _IMAGE_SINGLE_CLASSES):
        return _ImageView(cls)
    if issubclass(cls, fatass.Single):
        return _SingleView(cls)
    if issubclass(cls, fatass.Tuple):
        return _TupleView(cls)
    return cls


class _ChainItemView:
    def __init__(self, item):
        self._item = item

    def __getattr__(self, name):
        return _view_for(getattr(self._item, name))


class _ChainView:
    def __init__(self, obj):
        if isinstance(obj, type):
            self._cls = obj
            self._instance = obj()
        else:
            self._cls = type(obj)
            self._instance = obj

    def length(self):
        return self._cls.length()

    def __getitem__(self, i):
        return _ChainItemView(self._instance[i])


class _NodeView:
    def __init__(self, cls):
        self._cls = cls

    def __getattr__(self, name):
        child_cls = _import_node(f"{self._cls._topology_path()}.{name}")
        if issubclass(child_cls, fatass.Chain):
            return _ChainView(child_cls)
        return _view_for(child_cls)


def build(profile: Profile, projects: Projects, templates: Templates, template: str = "", scope: str = "present"):
    if template:
        print(f"build: searching templates for the first item named {template!r}")
        match_index = None
        for i in range(Templates.length()):
            item = Templates()[i]
            item_name = (item.info._assets_dir() / "name").read_text(encoding="utf-8").strip()
            if item_name == template:
                match_index = i
                break
        if match_index is None:
            raise ValueError(f"no template named {template!r} found in cv.templates")
    else:
        print("build: no template name given, using templates[0]")
        if Templates.length() == 0:
            raise ValueError("no templates found in cv.templates")
        match_index = 0

    template_item = Templates()[match_index]
    source_dir = template_item.source._assets_dir()
    out_dir = Draft._assets_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"build: copying {_GENERATOR} (and supporting assets) from templates[{match_index}]")
    for child in source_dir.iterdir():
        if child.name in ("main.aux", "main.log", "main.out", "main.pdf"):
            continue
        target = out_dir / child.name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)

    print(f"build: writing scope.py (scope={scope!r})")
    (out_dir / "scope.py").write_text(f"scope = {scope!r}\n", encoding="utf-8")

    generator_path = out_dir / _GENERATOR
    spec = importlib.util.spec_from_file_location("template", generator_path)
    template_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(template_module)

    print("build: rendering main.tex via the template's generate_tex()")
    tex = template_module.generate_tex(_NodeView(profile), _ChainView(projects), scope)
    tex = _sanitize_tex(tex)
    (out_dir / "main.tex").write_text(tex, encoding="utf-8")

    print("build: compiling main.tex with pdflatex")
    for _ in range(2):
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
            cwd=out_dir,
            check=True,
        )
    print("build: generated main.pdf in", out_dir)
