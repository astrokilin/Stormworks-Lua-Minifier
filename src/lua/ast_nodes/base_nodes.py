from __future__ import annotations
from collections.abc import Generator, KeysView, Iterator
from enum import Enum, auto
from typing import TextIO, TypeVar
from itertools import repeat

from lua.lexer import BufferedTokenStream

NodeFirst = set[str] | KeysView[str]


class AstNode:
    FIRST_CONTENTS: NodeFirst = set()
    FIRST_NAMES: NodeFirst = set()

    ERROR_NAME: str = ""

    __slots__ = ()

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

    # these methods should return descendants in reversed order
    def descendants(self) -> Iterator[AstNode]:
        return iter(())

    def parse_tree_descendants(self) -> Iterator[AstNode | str]:
        return iter(())

    # node, depth, descendant number of node, number of node descendants
    def dfs(
        self,
    ) -> Generator[tuple[AstNode, int, int, int], None, None]:
        stack: list[tuple[tuple[int, AstNode], int]] = [((0, self), 0)]
        while stack:
            (node_num, node), depth = stack.pop()
            d = len(stack)
            if isinstance(node, str):
                print(node)
            stack.extend(zip(enumerate(node.descendants()), repeat(depth + 1)))
            yield node, depth, node_num, len(stack) - d

    def terminals(self) -> Generator[str, None, None]:
        stack: list[AstNode | str] = [self]
        while stack:
            str_or_node = stack.pop()

            if isinstance(str_or_node, str):
                yield str_or_node
                continue

            stack.extend(str_or_node.parse_tree_descendants())

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
