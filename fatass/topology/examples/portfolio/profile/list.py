from fatass.topology.examples.portfolio.profile import Profile as Profile


def _read(path):
    return path.read_text(encoding="utf-8").strip()


def _print_tuple(dir_path):
    fields = sorted(p for p in dir_path.iterdir() if p.is_file() and p.name != ".gitkeep")
    for field in fields:
        print(f"{field.name}: {_read(field)}")


def _tuple_is_empty(dir_path):
    fields = [p for p in dir_path.iterdir() if p.is_file() and p.name != ".gitkeep"]
    return all(not _read(field) for field in fields)


def _print_chain(dir_path):
    current = dir_path
    index = 0
    while current is not None:
        entry_dir = current / "entry"
        if entry_dir.is_dir() and not _tuple_is_empty(entry_dir):
            print(f"[{index}]")
            _print_tuple(entry_dir)
            print()
            index += 1
        next_dir = current / ".next"
        current = next_dir if next_dir.is_dir() else None


def list(profile: Profile):
    root = profile._assets_dir()
    for item in sorted(root.iterdir()):
        if item.name == ".gitkeep":
            continue

        print(f"== {item.name} ==")

        if item.is_file():
            print(_read(item))
        elif (item / "entry").is_dir():
            _print_chain(item)
        else:
            single_files = [p for p in item.iterdir() if p.is_file() and p.name != ".gitkeep"]
            if len(single_files) == 1 and single_files[0].stem == "_":
                print(_read(single_files[0]))
            else:
                _print_tuple(item)

        print()
