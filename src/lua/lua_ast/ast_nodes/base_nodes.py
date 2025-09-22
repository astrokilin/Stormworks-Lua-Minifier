"""
This module contains all parent classes for lua abstact syntax tree
"""

from __future__ import annotations
from collections.abc import Generator, Iterator
from enum import Enum, auto
from typing import TypeVar

from lua.graph import TreeNode
from lua.lua_ast.parsing import Parsable


class AstNode(TreeNode):
    """represents lua abstract syntax tree (ast) node
    all ast nodes should inherit from this class
    and provide realization for its public methods
    """

    __slots__ = ()

    # simulate parse tree traversal

    # should return parse descendants in reversed order
    def parse_tree_descendants(self) -> Iterator[AstNode | str]:
        """should return parse descendants (nodes or strings) in reversed order"""
        return iter(())

    def terminals(self) -> Generator[str, None, None]:
        """convert ast node to term iterator"""

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


class DataNode(AstNode):
    """descendant of this node represents data"""

    __slots__ = ()

    class DataTypes(Enum):
        """enum for all lua types"""

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

    @property
    def data_type(self) -> DataNode.DataTypes:
        return DataNode.DataTypes.RUNTIME_DEPEND

    def __repr__(self):
        return super().__repr__() + f" datatype: {self.data_type}"


# Descendants of this node represents operations


class OperationNode(DataNode, Parsable):
    """descendants of this node represents operations"""

    _OPERATION_PRECEDENCE: dict[str, int] = {}
    _RIGHT_ASSOC_OPERATIONS: set[str] = {"..", "^"}

    __slots__ = ("opcode",)

    def __init__(self, opcode: str) -> None:
        self.opcode = opcode

    @classmethod
    def parsable_from_parser(cls, parser):
        return cls(opcode=next(parser.token_stream).content)

    def __repr__(self):
        return super().__repr__() + f" opcode: {self.opcode}"

    @property
    def precedence(self) -> int:
        """get precedence of the operation"""
        return self._OPERATION_PRECEDENCE[self.opcode]

    @property
    def right_associativity(self) -> bool:
        """check whether the operation is right associative"""
        return self.opcode in self._RIGHT_ASSOC_OPERATIONS
