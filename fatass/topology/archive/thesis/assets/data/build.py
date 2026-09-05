import shutil
from pathlib import Path

from .data import Data

SOURCES = [
    Path("/scratch/qi/project/data"),
    Path("/scratch/qi/project/results"),
]


def build():
    assets_dir = Data._assets_dir()

    print(f"clearing {assets_dir}")
    if assets_dir.exists():
        shutil.rmtree(assets_dir)
    assets_dir.mkdir(parents=True)

    for source in SOURCES:
        dest = assets_dir / source.name
        print(f"copying {source} -> {dest}")
        shutil.copytree(source, dest)
