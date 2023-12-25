from collections.abc import Iterable
from typing import Any


def iter_sep(seq: Iterable, sep: Any = ","):
    if seq:
        i = iter(seq)
        yield next(i)
        for j in i:
            yield sep
            yield j
