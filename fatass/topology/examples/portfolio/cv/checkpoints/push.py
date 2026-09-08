from fatass.topology.examples.portfolio.cv.draft import Draft as Draft
from fatass.topology.examples.portfolio.cv.checkpoints import Checkpoints as Checkpoints


def push(draft: Draft):
    print("push: reading draft's main.pdf")
    pdf_path = draft._assets_dir() / "main.pdf"
    if not pdf_path.is_file():
        raise FileNotFoundError(
            f"no main.pdf found in {pdf_path.parent} — build cv.draft first"
        )

    print("push: extending checkpoints with a new entry")
    Checkpoints.extend()
    index = Checkpoints.length() - 1
    item = Checkpoints()[index]

    print(f"push: writing checkpoints[{index}].file")
    item.file.write_bytes(pdf_path.read_bytes())

    print("push: done")
