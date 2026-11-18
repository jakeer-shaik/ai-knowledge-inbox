"""Keep only the sources an answer actually cites.

Retrieval sends the top-k passages to the model, but an answer usually cites only
some of them. Returning every retrieved passage as a "source" would credit text
that played no part in the answer, so citations are renumbered in order of first
use and uncited passages are dropped.
"""

import re

# [1]  [2][3]  [1, 2]
_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def keep_cited(answer: str, passage_count: int) -> tuple[str, list[int]]:
    """Return the answer with citations renumbered 1..n, and the original passage numbers in that order.

    Bracketed numbers that don't refer to a passage (e.g. "[2024]") are left untouched.
    """
    order: list[int] = []
    for match in _CITATION.finditer(answer):
        for number in _numbers(match.group(1)):
            if 1 <= number <= passage_count and number not in order:
                order.append(number)

    renumbered = {old: new for new, old in enumerate(order, start=1)}

    def rewrite(match: re.Match) -> str:
        numbers = _numbers(match.group(1))
        if not all(n in renumbered for n in numbers):
            return match.group(0)
        return "".join(f"[{renumbered[n]}]" for n in numbers)

    return _CITATION.sub(rewrite, answer), order


def _numbers(group: str) -> list[int]:
    return [int(part) for part in group.split(",")]
