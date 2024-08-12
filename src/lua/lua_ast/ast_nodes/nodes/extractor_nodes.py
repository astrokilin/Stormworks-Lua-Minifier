from __future__ import annotations
from typing import Self
from itertools import chain

from lua.lua_ast.lexer import BufferedTokenStream
from lua.lua_ast.parsing import (
    parsable_starts_with,
    TokenDispatchTable,
    ParsableSkipable,
    LuaParser,
)
from lua.lua_ast.runtime_routines import iter_sep
from lua.lua_ast.ast_nodes.base_nodes import AstNode

import lua.lua_ast.ast_nodes.nodes.data_nodes as data_nodes


class TableGetterNode(AstNode, ParsableSkipable):
    __slots__ = ("field_node",)

    def __init__(self, field_node: data_nodes.NameNode | data_nodes.ExpNode):
        self.field_node = field_node

    def descendants(self):
        return iter((self.field_node,))

    def parse_tree_descendants(self):
        if isinstance(self.field_node, data_nodes.ExpNode):
            return iter(("]", self.field_node, "["))

        return iter((self.field_node, "."))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"[", "."}
    PARSABLE_ERROR_NAME = "table field"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        t = next(parser.token_stream)
        field: data_nodes.NameNode | data_nodes.ExpNode

        if t.content == "[":
            (field,) = parser.parse_simple_rule((data_nodes.ExpNode, "]"), t.content)

        else:
            field = parser.parse_parsable(data_nodes.NameNode, t.content, True)

        return cls(field)

    @classmethod
    def parsable_skip_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> int:
        if stream.peek(index).content == ".":
            return data_nodes.NameNode.parsable_skip_in_stream(stream, index + 1)

        return stream.peek_matching_parenthesis("[", "]", index)


class MethodGetterNode(AstNode, ParsableSkipable):
    __slots__ = "name_node", "funcgetter_node"

    def __init__(self, name_node: data_nodes.NameNode, funcgetter_node: FuncGetterNode):
        self.name_node = name_node
        self.funcgetter_node = funcgetter_node

    def descendants(self):
        return iter((self.funcgetter_node, self.name_node))

    def parse_tree_descendants(self):
        return iter((self.funcgetter_node, self.name_node, ":"))

    PARSABLE_FIRST_TOKEN_CONTENTS = {":"}
    PARSABLE_ERROR_NAME = "method call"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        return cls(
            parser.parse_parsable(
                data_nodes.NameNode, next(parser.token_stream).content, True
            ),
            parser.parse_parsable(
                FuncGetterNode, data_nodes.NameNode.PARSABLE_ERROR_NAME, True
            ),
        )

    @classmethod
    def parsable_skip_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> int:
        if stream.peek(index).content in cls.PARSABLE_FIRST_TOKEN_CONTENTS:
            return FuncGetterNode.parsable_skip_in_stream(
                stream, data_nodes.NameNode.parsable_skip_in_stream(stream, index + 1)
            )

        return index


@parsable_starts_with(data_nodes.TableConstrNode)
class FuncGetterNode(AstNode, ParsableSkipable):
    __slots__ = ("arg",)

    def __init__(
        self,
        arg: list[data_nodes.ExpNode]
        | data_nodes.TableConstrNode
        | data_nodes.ConstNode,
    ):
        self.arg = arg

    def descendants(self):
        if isinstance(self.arg, list):
            return reversed(self.arg)

        return iter((self.arg,))

    def parse_tree_descendants(self):
        if isinstance(self.arg, list):
            return chain((")",), iter_sep(reversed(self.arg)), ("(",))

        return iter((self.arg,))

    _D_T_ARGS = TokenDispatchTable(
        dict.fromkeys(
            data_nodes.TableConstrNode.PARSABLE_FIRST_TOKEN_CONTENTS,
            data_nodes.TableConstrNode,
        ),
        {"string": data_nodes.ConstNode},
    )

    PARSABLE_FIRST_TOKEN_CONTENTS = {"("}
    PARSABLE_FIRST_TOKEN_NAMES = {"string"}
    PARSABLE_ERROR_NAME = "function call"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        arg: list[
            data_nodes.ExpNode
        ] | data_nodes.TableConstrNode | data_nodes.ConstNode

        if (node_type := cls._D_T_ARGS[stream.peek()]) is not None:
            arg = parser.parse_parsable(node_type)
        else:
            err_name = next(stream).content

            arg = list(parser.parse_list(data_nodes.ExpNode))
            if arg:
                err_name = arg[-1].PARSABLE_ERROR_NAME

            parser.parse_terminal(")", err_name)

        return cls(arg)

    @classmethod
    def parsable_skip_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> int:
        t = stream.peek(index)

        if t.name in cls.PARSABLE_FIRST_TOKEN_NAMES:
            return index + 1

        if t.content == "(":
            return stream.peek_matching_parenthesis("(", ")", index)

        return data_nodes.TableConstrNode.parsable_skip_in_stream(stream, index)
