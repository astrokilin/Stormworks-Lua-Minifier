from collections.abc import Iterator, Callable
from typing import Any

from lua.ast_nodes.base_nodes import AstNode, AstNodeType


def iter_sep(seq: Iterator[Any], sep: Any = ","):
    if (t := next(seq, None)) is not None:
        yield t
        for j in seq:
            yield sep
            yield j


def starts_with(
    *starting_nonterms: type[AstNode],
) -> Callable[[type[AstNodeType]], type[AstNodeType]]:
    def decorate(orig_class: type[AstNodeType]):
        for nonterm_class in starting_nonterms:
            # I guess sometimes we can just link
            # to a existing set without creating a copy
            if not orig_class.FIRST_CONTENTS:
                orig_class.FIRST_CONTENTS = nonterm_class.FIRST_CONTENTS
            elif nonterm_class.FIRST_CONTENTS:
                orig_class.FIRST_CONTENTS |= nonterm_class.FIRST_CONTENTS

            if not orig_class.FIRST_NAMES:
                orig_class.FIRST_NAMES = nonterm_class.FIRST_NAMES
            elif nonterm_class.FIRST_NAMES:
                orig_class.FIRST_NAMES |= nonterm_class.FIRST_NAMES

        return orig_class

    return decorate
