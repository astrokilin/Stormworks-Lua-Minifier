from __future__ import annotations
from collections.abc import Generator, Callable, KeysView, Sequence
from enum import Enum, auto
from typing import TextIO, TypeVar
from itertools import repeat

from lua.lexer import BufferedTokenStream

NodeFirst = set[str] | KeysView[str]


class AstNode:
    FIRST_CONTENTS: NodeFirst = set()
    FIRST_NAMES: NodeFirst = set()

    ERROR_NAME: str = ""

    __slots__: tuple = ()

    def __init__(self):
        pass

    # methods for tree parsing

    # this method construct node from token stream
    # It should be called only when u can guarantee that it will get right first token
    @classmethod
    def from_tokens(cls: type[AstNodeType], stream: BufferedTokenStream) -> AstNodeType:
        next(stream)
        return cls()

    @classmethod
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0) -> bool:
        t = stream.peek(index)
        return t.content in cls.FIRST_CONTENTS or t.name in cls.FIRST_NAMES

    # methods for tree traversal

    # maybe implementing this method for every node would be better but im too lazy
    def descendants(self) -> Generator[AstNode, None, None]:
        for i in self.__slots__:
            match unit := getattr(self, i):
                case list():
                    yield from unit

                case AstNode():
                    yield unit

    # node, depth, descendant number of node, number of node descendants
    def dfs(
        self,
    ) -> Generator[tuple[AstNode, int, int, int], None, None]:
        stack = [((0, self), 0)]
        while stack:
            t = stack.pop()
            d = tuple(t[0][1].descendants())

            yield t[0][1], t[1], t[0][0], len(d)
            stack.extend(zip(enumerate(reversed(d)), repeat(t[1])))

    # methods for converting tree to text

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return ()

    def terminals(self) -> Generator[str, None, None]:
        stack = [self]
        while stack:
            tup = stack.pop()

            if isinstance(tup, str):
                yield tup
                continue

            stack.extend(reversed(tup.get_parse_tree_descendants()))

    def __repr__(self):
        return self.__class__.__name__

    def __str__(self):
        return " ".join(self.terminals())


AstNodeType = TypeVar("AstNodeType", bound=AstNode, covariant=True)


# Descendant of this node represents data
# It should be possible for data to get its type


class DataNode(AstNode):
    __slots__ = ()

    class DataTypes(Enum):
        NIL = auto()
        BOOLEAN = auto()
        FUNCTION = auto()
        TABLE = auto()
        STRING = auto()
        NUMBER_FLOAT = auto()
        NUMBER_INT = auto()
        VARARG = auto()
        RUNTIME_DEPEND = auto()

    # runtime depend types means that
    # value and type should be obtained from the runtime

    def get_type(self) -> DataNode.DataTypes:
        return DataNode.DataTypes.RUNTIME_DEPEND

    def __repr__(self):
        return super().__repr__() + f" datatype: {self.get_type()}"


# Descendants of this node represents operations


class OperationNode(DataNode):
    _OPERATION_PRECEDENCE: dict[str, int] = {}
    _RIGHT_ASSOC_OPERATIONS: set[str] = {"..", "^"}

    __slots__ = ("opcode",)

    def __init__(self, opcode: str):
        self.opcode = opcode

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        return cls(opcode=next(stream).content)

    def __repr__(self):
        return super().__repr__() + f" opcode: {self.opcode}"

    def get_precedence(self) -> int:
        return self._OPERATION_PRECEDENCE[self.opcode]

    def is_right_assoc(self) -> bool:
        return self.opcode in self._RIGHT_ASSOC_OPERATIONS


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
