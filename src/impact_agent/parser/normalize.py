def normalise_lines(text: str) -> tuple[list[str], list[str]]:
    """Split the exact text and build a same-length normalised copy for matching.

    `lines` is `text.split("\\n")` (positions in the parsed result index into it, contract
    section 4). Each `norm` line has leading form feeds, surrounding whitespace and a trailing
    carriage return removed. The original text is never modified.
    """
    lines = text.split("\n")
    return lines, [line.strip() for line in lines]


def collapse(text: str) -> str:
    return " ".join(text.split())
