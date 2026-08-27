import shutil

from fatass.topology.thesis.experiment.code import Code as Code
from fatass.topology.thesis.experiment.code_morph import CodeMorph as CodeMorph


def build(code: Code):
    dest = CodeMorph()._assets_dir()
    src = code._assets_dir()

    print("build: erasing code_morph")
    for item in dest.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    print("build: copying code into code_morph")
    for item in src.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    print("build: copy complete")
