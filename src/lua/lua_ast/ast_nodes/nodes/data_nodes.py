from __future__ import annotations
from typing import Self
from itertools import chain

from lua.lua_ast.lexer import BufferedTokenStream
from lua.lua_ast.exceptions import WrongTokenError
from lua.lua_ast.ast_nodes.base_nodes import (
    AstNode,
    DataNode,
    OperationNode,
)
from lua.lua_ast.parsing import (
    Parsable,
    ParsableSkipable,
    parsable_starts_with,
    LuaParser,
    TokenDispatchTable,
)
from lua.lua_ast.runtime_routines import iter_sep


class NameNode(DataNode, ParsableSkipable):
    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = name

    def parse_tree_descendants(self):
        return iter((self.name,))

    def __repr__(self):
        return super().__repr__() + f" name: {self.name}"

    PARSABLE_FIRST_TOKEN_NAMES = {"id"}
    PARSABLE_ERROR_NAME = "variable name"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        return cls(name=next(parser.token_stream).content)

    @classmethod
    def parsable_skip_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> int:
        return (
            index + 1
            if stream.peek(index).name in cls.PARSABLE_FIRST_TOKEN_NAMES
            else index
        )


class VarargNode(DataNode, Parsable):
    __slots__ = ()

    def parse_tree_descendants(self):
        return iter(("...",))

    @property
    def data_type(self):
        return DataNode.DataTypes.VARARG

    PARSABLE_FIRST_TOKEN_CONTENTS = {"..."}
    PARSABLE_ERROR_NAME = "vararg expression"


class ConstNode(DataNode, Parsable):
    __slots__ = "value", "__d_type"

    def __init__(self, value: str, data_type: DataNode.DataTypes):
        self.value = value
        self.__d_type = data_type

    def parse_tree_descendants(self):
        return iter((self.value,))

    def __repr__(self):
        return super().__repr__() + f" value: {self.value}"

    @property
    def data_type(self):
        return self.__d_type

    _D_T_TYPES = TokenDispatchTable(
        {
            "nil": DataNode.DataTypes.NIL,
            "true": DataNode.DataTypes.BOOLEAN,
            "false": DataNode.DataTypes.BOOLEAN,
        },
        {
            "string": DataNode.DataTypes.STRING,
            "numeral": DataNode.DataTypes.NUMBER_INT,
        },
    )

    PARSABLE_FIRST_TOKEN_CONTENTS = _D_T_TYPES.contents.keys()
    PARSABLE_FIRST_TOKEN_NAMES = _D_T_TYPES.names.keys()
    PARSABLE_ERROR_NAME = "consant variable"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        t = next(parser.token_stream)
        d_type: DataNode.DataTypes = cls._D_T_TYPES[t]  # type: ignore

        # float check
        if d_type == DataNode.DataTypes.NUMBER_INT:
            for lit in t.content:
                if lit in {".", "p", "P", "e", "E"}:
                    d_type = DataNode.DataTypes.NUMBER_FLOAT
                    break

        return cls(t.content, d_type)


class TableConstrNode(DataNode, ParsableSkipable):
    __slots__ = ("field_node_list",)

    def __init__(self, field_node_list: list[FieldNode]):
        self.field_node_list = field_node_list

    def descendants(self):
        return reversed(self.field_node_list)

    def parse_tree_descendants(self):
        return chain(("}",), iter_sep(reversed(self.field_node_list)), ("{",))

    @property
    def data_type(self):
        return DataNode.DataTypes.TABLE

    PARSABLE_FIRST_TOKEN_CONTENTS: set = {"{"}
    PARSABLE_ERROR_NAME = "table constructor"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        field_node_list: list[FieldNode] = []
        # skip {
        err_name = next(stream).content

        # fill fieldlist if it exist
        if FieldNode.parsable_presented_in_stream(stream):
            field_separators = {",", ";"}
            field_node_list.extend(parser.parse_list(FieldNode, field_separators))
            err_name = field_node_list[-1].PARSABLE_ERROR_NAME

            if stream.peek().content in field_separators:
                err_name = next(stream).content

        parser.parse_terminal("}", err_name)
        return cls(field_node_list)

    @classmethod
    def parsable_skip_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> int:
        return stream.peek_matching_parenthesis("{", "}", index)


import lua.lua_ast.ast_nodes.nodes.extractor_nodes as extractor_nodes


@parsable_starts_with(NameNode)
class PrefExpNode(DataNode, ParsableSkipable):
    __slots__ = "var_node", "extractor_node_list"

    def __init__(
        self, var_node: NameNode | ExpNode, extractor_node_list: list[AstNode]
    ):
        self.var_node = var_node
        self.extractor_node_list = extractor_node_list

    def descendants(self):
        return chain(reversed(self.extractor_node_list), (self.var_node,))

    def parse_tree_descendants(self):
        if isinstance(self.var_node, ExpNode):
            return chain(reversed(self.extractor_node_list), (")", self.var_node, "("))

        else:
            return chain(reversed(self.extractor_node_list), (self.var_node,))

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
        if NameNode.parsable_presented_in_stream(stream):
            var = parser.parse_parsable(NameNode)
        else:
            (var,) = parser.parse_simple_rule((ExpNode, ")"), next(stream).content)

        extractor_node_list = []
        # now parse all extractor_nodes
        while (ext_type := cls._D_T_EXTRACTORS[stream.peek()]) is not None:
            extractor_node_list.append(parser.parse_parsable(ext_type))

        return cls(var, extractor_node_list)

    # return index of first token of last extractor
    # if no extractors will return index of first token
    # before Name | ( exp ) rule
    @classmethod
    def skip_to_last_ext(cls, stream: BufferedTokenStream, index: int = 0) -> int:
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
class VarNode(PrefExpNode, Parsable):
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


class FuncDefNode(DataNode, Parsable):
    __slots__ = ("funcbody_node",)

    def __init__(
        self,
        funcbody_node: function_nodes.FuncBodyNode,
    ):
        self.funcbody_node = funcbody_node

    def descendants(self):
        return iter((self.funcbody_node,))

    def parse_tree_descendants(self):
        return iter(
            (
                self.funcbody_node,
                "function",
            )
        )

    @property
    def data_type(self):
        return DataNode.DataTypes.FUNCTION

    PARSABLE_FIRST_TOKEN_CONTENTS = {"function"}
    PARSABLE_ERROR_NAME = "function definition"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        return cls(
            parser.parse_parsable(
                function_nodes.FuncBodyNode, next(parser.token_stream).content, True
            )
        )


import lua.lua_ast.ast_nodes.nodes.operation_nodes as operation_nodes


def _stack_form_binops(
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

        if isinstance(op, operation_nodes.BinOpNode):
            op.left_operand_node = exp_stack.pop()

        exp_stack.append(op)


@parsable_starts_with(
    ConstNode,
    PrefExpNode,
    VarargNode,
    FuncDefNode,
    TableConstrNode,
    operation_nodes.UnOpNode,
)
class ExpNode(DataNode, Parsable):
    __slots__ = ("data_node",)

    def __init__(self, data_node: DataNode | OperationNode):
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
        exp_stack: list[DataNode | OperationNode] = []

        while True:
            while operation_nodes.UnOpNode.parsable_presented_in_stream(stream):
                exp_stack.append(parser.parse_parsable(operation_nodes.UnOpNode))

            if (operand_type := cls._D_T_OPERAND[stream.peek()]) is None:
                t = next(stream)
                raise WrongTokenError(t.content, t.pos, "operand")

            exp_stack.append(parser.parse_parsable(operand_type))

            if operation_nodes.BinOpNode.parsable_presented_in_stream(stream):
                next_op = parser.parse_parsable(operation_nodes.BinOpNode)
                _stack_form_binops(next_op.precedence, exp_stack)
                exp_stack.append(next_op)

            else:
                _stack_form_binops(-1, exp_stack)
                break

        return cls(exp_stack.pop())


@parsable_starts_with(ExpNode, NameNode)
class FieldNode(DataNode, Parsable):
    __slots__ = "index_node", "exp_node"

    def __init__(self, index_node: ExpNode | NameNode | None, exp_node: ExpNode):
        self.index_node = index_node
        self.exp_node = exp_node

    def descendants(self):
        if self.index_node is not None:
            return iter((self.exp_node, self.index_node))

        return iter((self.exp_node,))

    def parse_tree_descendants(self):
        match self.index_node:
            case ExpNode():
                return iter((self.exp_node, "=", "]", self.index_node, "["))

            case NameNode():
                return iter((self.exp_node, "=", self.index_node))

            case None:
                return iter((self.exp_node,))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"["}
    PARSABLE_ERROR_NAME = "table constructor field"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        index_node = None

        if stream.peek().content == "[":
            (index_node,) = parser.parse_simple_rule(
                (ExpNode, "]", "="), next(stream).content
            )

        elif stream.peek(1).content == "=":
            index_node = parser.parse_parsable(NameNode)
            next(stream)

        err_name = "=" if index_node is not None else ""

        return cls(index_node, parser.parse_parsable(ExpNode, err_name, True))
