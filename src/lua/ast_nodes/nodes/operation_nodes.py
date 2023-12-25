from __future__ import annotations
from collections.abc import Generator, Sequence

from lua.ast_nodes.base_nodes import AstNode, DataNode, OperationNode
from lua.parsing_routines import TokenDispatchTable


class BinOpNode(OperationNode):
    _OPERATION_PRECEDENCE = {
        "or": 0,
        "and": 1,
        "<": 2,
        ">": 2,
        "<=": 2,
        ">=": 2,
        "~=": 2,
        "==": 2,
        "|": 3,
        "~": 4,
        "&": 5,
        "<<": 6,
        ">>": 6,
        "..": 7,
        "+": 8,
        "-": 8,
        "*": 9,
        "/": 9,
        "//": 9,
        "%": 9,
        "^": 11,
    }

    FIRST_CONTENTS = _OPERATION_PRECEDENCE.keys()

    ERROR_NAME = "binary operation"

    __slots__ = "left_operand_node", "right_operand_node"

    def __init__(
        self,
        left_operand_node: DataNode | None = None,
        right_operand_node: DataNode | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.left_operand_node = left_operand_node
        self.right_operand_node = right_operand_node

    # ExpNode parsing algorithm will always fill left, right operands so we dont listen mypy here
    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return self.left_operand_node, self.opcode, self.right_operand_node  # type: ignore


class UnOpNode(OperationNode):
    _OPERATION_PRECEDENCE = {"-": 10, "not": 10, "#": 10, "~": 10}

    FIRST_CONTENTS = _OPERATION_PRECEDENCE.keys()

    ERROR_NAME = "unary operation"

    __slots__ = ("right_operand_node",)

    def __init__(self, right_operand_node: DataNode | None = None, **kwargs):
        super().__init__(**kwargs)
        self.right_operand_node = right_operand_node

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return self.opcode, self.right_operand_node  # type: ignore
