from __future__ import annotations
from typing import Self
from itertools import chain
from enum import Enum, auto

from lua.lua_ast.lexer import BufferedTokenStream
from lua.lua_ast.exceptions import WrongTokenError
from lua.lua_ast.ast_nodes.base_nodes import AstNode, OperationNode
from lua.lua_ast.parsing import (
    Parsable,
    ParsableSkipable,
    parsable_starts_with,
    LuaParser,
    TokenDispatchTable,
)
from lua.lua_ast.runtime_routines import iter_sep


class NameNode(AstNode, ParsableSkipable):
    __slots__ = ("name",)

    def __init__(self, start_index: int, end_index: int, name: str) -> None:
        super().__init__(start_index, end_index)
        self.name = name

    def parse_tree_descendants(self):
        return iter((self.name,))

    def __repr__(self):
        return super().__repr__() + f" name: {self.name}"

    PARSABLE_FIRST_TOKEN_NAMES = {"id"}
    PARSABLE_ERROR_NAME = "variable name"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        pos_start = parser.token_stream.peek().pos
        t = next(parser.token_stream)
        return cls(
            t.pos,
            parser.token_stream.last_pos,
            t.content,
        )

    @classmethod
    def parsable_skip_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> int:
        return (
            index + 1
            if stream.peek(index).name in cls.PARSABLE_FIRST_TOKEN_NAMES
            else index
        )


class VarargNode(AstNode, Parsable):
    __slots__ = ()

    def parse_tree_descendants(self):
        return iter(("...",))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"..."}
    PARSABLE_ERROR_NAME = "vararg expression"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        t = next(parser.token_stream)
        return cls(t.pos, parser.token_stream.last_pos)


class ConstNode(AstNode, Parsable):
    __slots__ = "value", "d_type"

    class ConstDataTypes(Enum):
        """enum for const lua types"""

        NIL = auto()
        BOOLEAN = auto()
        STRING = auto()
        NUMBER_FLOAT = auto()
        NUMBER_INT = auto()

    def __init__(
        self, start_index: int, end_index: int, value: str, data_type: ConstDataTypes
    ) -> None:
        super().__init__(start_index, end_index)
        self.value = value
        self.d_type = data_type

    def parse_tree_descendants(self):
        return iter((self.value,))

    def __repr__(self):
        return super().__repr__() + f" value: {self.value}"

    _D_T_TYPES = TokenDispatchTable(
        {
            "nil": ConstDataTypes.NIL,
            "true": ConstDataTypes.BOOLEAN,
            "false": ConstDataTypes.BOOLEAN,
        },
        {
            "string": ConstDataTypes.STRING,
            "numeral": ConstDataTypes.NUMBER_INT,
        },
    )

    PARSABLE_FIRST_TOKEN_CONTENTS = _D_T_TYPES.contents.keys()
    PARSABLE_FIRST_TOKEN_NAMES = _D_T_TYPES.names.keys()
    PARSABLE_ERROR_NAME = "consant variable"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        t = next(parser.token_stream)
        d_type: ConstNode.ConstDataTypes = cls._D_T_TYPES[t]  # type: ignore

        # float check
        if d_type == ConstNode.ConstDataTypes.NUMBER_INT:
            for lit in t.content:
                if lit in {".", "p", "P", "e", "E"}:
                    d_type = ConstNode.ConstDataTypes.NUMBER_FLOAT
                    break

        return cls(t.pos, parser.token_stream.last_pos, t.content, d_type)


class TableConstrNode(AstNode, ParsableSkipable):
    __slots__ = ("field_node_list",)

    def __init__(
        self, start_index: int, end_index: int, field_node_list: list[FieldNode]
    ) -> None:
        super().__init__(start_index, end_index)
        self.field_node_list = field_node_list

    def descendants(self):
        return reversed(self.field_node_list)

    def parse_tree_descendants(self):
        return chain(("{",), iter_sep(iter(self.field_node_list)), ("}",))

    PARSABLE_FIRST_TOKEN_CONTENTS: set = {"{"}
    PARSABLE_ERROR_NAME = "table constructor"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        field_node_list: list[FieldNode] = []
        # skip {
        t = next(stream)
        err_name = t.content

        # fill fieldlist if it exist
        if FieldNode.parsable_presented_in_stream(stream):
            field_separators = {",", ";"}
            field_node_list.extend(parser.parse_list(FieldNode, field_separators))
            err_name = field_node_list[-1].PARSABLE_ERROR_NAME

            if stream.peek().content in field_separators:
                err_name = next(stream).content

        parser.parse_terminal("}", err_name)
        return cls(t.pos, stream.last_pos, field_node_list)

    @classmethod
    def parsable_skip_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> int:
        return stream.peek_matching_parenthesis("{", "}", index)


import lua.lua_ast.ast_nodes.nodes.extractor_nodes as extractor_nodes


@parsable_starts_with(NameNode)
class PrefExpNode(AstNode, ParsableSkipable):
    __slots__ = "var_node", "extractor_node_list"

    def __init__(
        self,
        start_index: int,
        end_index: int,
        var_node: NameNode | ExpNode,
        extractor_node_list: list[
            extractor_nodes.TableGetterNode
            | extractor_nodes.MethodGetterNode
            | extractor_nodes.FuncGetterNode
        ],
    ) -> None:
        super().__init__(start_index, end_index)
        self.var_node = var_node
        self.extractor_node_list = extractor_node_list

    def descendants(self):
        return chain(reversed(self.extractor_node_list), (self.var_node,))

    def parse_tree_descendants(self):
        if isinstance(self.var_node, ExpNode):
            return chain(("(", self.var_node, ")"), self.extractor_node_list)

        return chain((self.var_node,), self.extractor_node_list)

    _D_T_EXTRACTORS = TokenDispatchTable.dispatch_types(
        extractor_nodes.TableGetterNode,
        extractor_nodes.FuncGetterNode,
        extractor_nodes.MethodGetterNode,
    )

    PARSABLE_FIRST_TOKEN_CONTENTS = {"("}
    PARSABLE_ERROR_NAME = "prefix expression"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        pos_start = stream.peek().pos

        if NameNode.parsable_presented_in_stream(stream):
            var = parser.parse_parsable(NameNode)
        else:
            (var,) = parser.parse_simple_rule((ExpNode, ")"), next(stream).content)

        extractor_node_list = []
        # now parse all extractor_nodes
        while (ext_type := cls._D_T_EXTRACTORS[stream.peek()]) is not None:
            extractor_node_list.append(parser.parse_parsable(ext_type))

        return cls(pos_start, stream.last_pos, var, extractor_node_list)

    @classmethod
    def skip_to_last_ext(cls, stream: BufferedTokenStream, index: int = 0) -> int:
        """return index of first token of last extractor
        if no extractors will return index of first token
        before Name | ( exp ) rule
        """

        new_index = NameNode.parsable_skip_in_stream(stream, index)

        if new_index == index:
            new_index = stream.peek_matching_parenthesis("(", ")", index)

        # if we havent moved -> there is no prefexp in stream
        if new_index == index:
            return index

        # now get position of the last extractor
        if (last_extractor := cls._D_T_EXTRACTORS[stream.peek(new_index)]) is not None:
            while True:
                index = last_extractor.parsable_skip_in_stream(stream, new_index)
                if (next_extractor := cls._D_T_EXTRACTORS[stream.peek(index)]) is None:
                    break

                new_index = index
                last_extractor = next_extractor

        return new_index

    @classmethod
    def parsable_skip_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> int:
        new_index = cls.skip_to_last_ext(stream, index)

        # have we moved?
        if new_index == index:
            return index

        if (last_extractor := cls._D_T_EXTRACTORS[stream.peek(new_index)]) is not None:
            new_index = last_extractor.parsable_skip_in_stream(stream, new_index)

        return new_index


# var node is just PrefExpNode which ends with table extractor or
# PrefExpNode with var = NameNode and no extractors
class VarNode(PrefExpNode):
    __slots__ = ()

    PARSABLE_ERROR_NAME = "variable"

    @classmethod
    def parsable_presented_in_stream(cls, stream, index=0):
        # VarNode is PrefExpNode with var = name and extractors = []
        # or just PrefExpNode with extractors[-1] = TableGetterNode

        last_ext_offset = cls.skip_to_last_ext(stream, index)

        if extractor_nodes.TableGetterNode.parsable_presented_in_stream(
            stream, last_ext_offset
        ):
            return True

        return NameNode.parsable_presented_in_stream(stream, index)


import lua.lua_ast.ast_nodes.nodes.function_nodes as function_nodes


class FuncDefNode(AstNode, Parsable):
    __slots__ = ("funcbody_node",)

    def __init__(
        self,
        start_index: int,
        end_index: int,
        funcbody_node: function_nodes.FuncBodyNode,
    ) -> None:
        super().__init__(start_index, end_index)
        self.funcbody_node = funcbody_node

    def descendants(self):
        return iter((self.funcbody_node,))

    def parse_tree_descendants(self):
        return iter(
            (
                "function",
                self.funcbody_node,
            )
        )

    PARSABLE_FIRST_TOKEN_CONTENTS = {"function"}
    PARSABLE_ERROR_NAME = "function definition"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        pos_start = parser.token_stream.peek().pos
        node = parser.parse_parsable(
            function_nodes.FuncBodyNode, next(parser.token_stream).content, True
        )
        return cls(pos_start, parser.token_stream.last_pos, node)


import lua.lua_ast.ast_nodes.nodes.operation_nodes as operation_nodes


@parsable_starts_with(
    ConstNode,
    PrefExpNode,
    VarargNode,
    FuncDefNode,
    TableConstrNode,
    operation_nodes.UnOpNode,
)
class ExpNode(AstNode, Parsable):
    @staticmethod
    def __stack_form_binops(
        top_precedence: int,
        exp_stack: list,
    ):
        while len(exp_stack) > 1 and (
            exp_stack[-2].precedence > top_precedence
            or exp_stack[-2].precedence == top_precedence
            and exp_stack[-2].right_associativity
        ):
            d_2 = exp_stack.pop()
            op = exp_stack.pop()

            op.right_operand_node = d_2
            op.end_index = d_2.end_index

            if isinstance(op, operation_nodes.BinOpNode):
                op.left_operand_node = exp_stack.pop()
                op.start_index = op.left_operand_node.start_index

            exp_stack.append(op)

    __slots__ = ("data_node",)

    def __init__(
        self,
        start_index: int,
        end_index: int,
        data_node: ConstNode
        | VarargNode
        | FuncDefNode
        | PrefExpNode
        | TableConstrNode
        | OperationNode,
    ) -> None:
        super().__init__(start_index, end_index)
        self.data_node = data_node

    def descendants(self):
        return iter((self.data_node,))

    def parse_tree_descendants(self):
        return iter((self.data_node,))

    _D_T_OPERAND = TokenDispatchTable.dispatch_types(
        ConstNode, PrefExpNode, TableConstrNode, FuncDefNode, VarargNode
    )

    PARSABLE_ERROR_NAME = "expression"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        pos_start = stream.peek().pos
        exp_stack: list[
            ConstNode
            | VarargNode
            | FuncDefNode
            | PrefExpNode
            | TableConstrNode
            | OperationNode
        ] = []

        while True:
            while operation_nodes.UnOpNode.parsable_presented_in_stream(stream):
                exp_stack.append(parser.parse_parsable(operation_nodes.UnOpNode))

            if (operand_type := cls._D_T_OPERAND[stream.peek()]) is None:
                t = next(stream)
                raise WrongTokenError(t.name, t.content, t.pos, "operand")

            exp_stack.append(parser.parse_parsable(operand_type))

            if operation_nodes.BinOpNode.parsable_presented_in_stream(stream):
                next_op = parser.parse_parsable(operation_nodes.BinOpNode)
                ExpNode.__stack_form_binops(next_op.precedence, exp_stack)
                exp_stack.append(next_op)

            else:
                ExpNode.__stack_form_binops(-1, exp_stack)
                break

        return cls(pos_start, stream.last_pos, exp_stack.pop())


@parsable_starts_with(ExpNode, NameNode)
class FieldNode(AstNode, Parsable):
    __slots__ = "index_node", "exp_node"

    def __init__(
        self,
        start_index: int,
        end_index: int,
        index_node: ExpNode | NameNode | None,
        exp_node: ExpNode,
    ) -> None:
        super().__init__(start_index, end_index)
        self.index_node = index_node
        self.exp_node = exp_node

    def descendants(self):
        if self.index_node is not None:
            return iter((self.exp_node, self.index_node))

        return iter((self.exp_node,))

    def parse_tree_descendants(self):
        match self.index_node:
            case ExpNode():
                return iter(("[", self.index_node, "]", "=", self.exp_node))

            case NameNode():
                return iter((self.index_node, "=", self.exp_node))

            case None:
                return iter((self.exp_node,))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"["}
    PARSABLE_ERROR_NAME = "table constructor field"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        pos_start = stream.peek().pos
        index_node = None

        if stream.peek().content == "[":
            (index_node,) = parser.parse_simple_rule(
                (ExpNode, "]", "="), next(stream).content
            )

        elif stream.peek(1).content == "=":
            index_node = parser.parse_parsable(NameNode)
            next(stream)

        err_name = "=" if index_node is not None else ""

        return cls(
            pos_start,
            stream.last_pos,
            index_node,
            parser.parse_parsable(ExpNode, err_name, True),
        )


DataNodeT = (
    ConstNode | VarargNode | FuncDefNode | PrefExpNode | TableConstrNode | OperationNode
)
