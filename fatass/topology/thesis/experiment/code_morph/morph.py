import fatass


def morph():
    print("morph: entering free session to morph the code base")
    fatass.free(
        readable=[],
        prompt=(
            "This directory holds a copy of a code base (populated by this "
            "node's build transform). Morph the code base: work with me here "
            "to transform it into a meaningfully different variant of the "
            "same program, editing the files in this directory directly."
        ),
    )
    print("morph: free session complete")
