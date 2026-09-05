import shutil
import subprocess
import urllib.request
from pathlib import Path

import fatass
from fatass.topology.cv.projects import Projects as Projects


def push(path: str = "", url: str = ""):
    print("push: starting")
    Projects.extend()
    index = Projects.length() - 1
    target_dir = Projects()[index]._assets_dir()

    if path:
        src = Path(path)
        dest = target_dir / src.name
        print(f"push: copying {src} -> {dest}")
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)

    if url:
        if "github.com" in url:
            dest = target_dir / (Path(url).stem or "repo")
            print(f"push: cloning {url} -> {dest}")
            subprocess.run(["git", "clone", url, str(dest)], check=True)
        else:
            dest = target_dir / (Path(url).name or "download")
            print(f"push: fetching {url} -> {dest}")
            urllib.request.urlretrieve(url, dest)

    print("push: running init on info, summary")
    fatass.run_transform(f"cv.projects[{index}].info", "init")
    fatass.run_transform(f"cv.projects[{index}].summary", "init")

    print("push: done")
