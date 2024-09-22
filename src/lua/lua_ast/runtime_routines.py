from collections.abc import Iterator
from typing import Any


def iter_sep(seq: Iterator[Any], sep: Any = ","):
    """insert sep after each value from seq"""

    if (t := next(seq, None)) is not None:
        yield t
        for j in seq:
            yield sep
            yield j
