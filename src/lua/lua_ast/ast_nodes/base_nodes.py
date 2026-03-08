"""
This module contains all parent classes for lua abstact syntax tree
"""

from __future__ import annotations
from collections.abc import Iterator

from lua.graph import TreeNode
from lua.lua_ast.parsing import Parsable


class AstNode(TreeNode):
    """represents lua abstract syntax tree (ast) node
    all ast nodes should inherit from this class
    and provide realization for its public methods
    """

    __slots__ = "start_index", "end_index"

    def __init__(self, start_index: int, end_index: int):
        self.start_index = start_index
        self.end_index = end_index

    # simulate parse tree traversal

    # should return parse descendants in reversed order
    def parse_tree_descendants(self) -> Iterator[AstNode | str]:
        """should return parse descendants (nodes or strings) in reversed order"""
        return iter(())

    def __repr__(self):
        return f"{self.__class__.__name__} ({self.start_index}: {self.end_index})"


class OperationNode(AstNode, Parsable):
    """descendants of this node represents operations"""

    _OPERATION_PRECEDENCE: dict[str, int] = {}
    _RIGHT_ASSOC_OPERATIONS: set[str] = {"..", "^"}

    __slots__ = ("opcode",)

    def __init__(self, index: int, length: int, opcode: str) -> None:
        super().__init__(index, length)
        self.opcode = opcode

    @classmethod
    def parsable_from_parser(cls, parser):
        t = next(parser.token_stream)
        return cls(t.pos, t.pos + len(t.content), t.content)

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
