from __future__ import annotations
from collections.abc import Iterator
from itertools import chain

from lua.lexer import BufferedTokenStream
from lua.ast_nodes.base_nodes import AstNode, NodeFirst
from lua.parsing_routines import (
    skip_parenthesis,
    TokenDispatchTable,
    parse_node_list,
    parse_simple_rule,
    parse_terminal,
    parse_node,
)
from lua.runtime_routines import iter_sep, starts_with

import lua.ast_nodes.nodes.data_nodes as data_nodes


class TableGetterNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"[", "."}

    ERROR_NAME: str = "table field"

    __slots__ = ("field_node",)

    def __init__(self, field_node: data_nodes.NameNode | data_nodes.ExpNode):
        self.field_node = field_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        t = next(stream)
        field: data_nodes.NameNode | data_nodes.ExpNode
        if t.content == "[":
            (field,) = parse_simple_rule(stream, (data_nodes.ExpNode, "]"), t.content)

        else:
            field = parse_node(stream, data_nodes.NameNode, t.content)

        return cls(field)

    @staticmethod
    def skip(stream: BufferedTokenStream, index: int = 0) -> int:
        if stream.peek(index).content == ".":
            return data_nodes.NameNode.skip(stream, index + 1)

        return skip_parenthesis(stream, "[", "]", index)

    def descendants(self):
        return iter((self.field_node,))

    def parse_tree_descendants(self):
        if isinstance(self.field_node, data_nodes.ExpNode):
            return iter(("]", self.field_node, "["))

        return iter((self.field_node, "."))


class MethodGetterNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {":"}

    ERROR_NAME: str = "method call"

    __slots__ = "name_node", "funcgetter_node"

    def __init__(self, name_node: data_nodes.NameNode, funcgetter_node: FuncGetterNode):
        self.name_node = name_node
        self.funcgetter_node = funcgetter_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        return cls(
            parse_node(stream, data_nodes.NameNode, next(stream).content),
            parse_node(stream, FuncGetterNode, data_nodes.NameNode.ERROR_NAME),
        )

    @classmethod
    def skip(cls, stream: BufferedTokenStream, index: int = 0) -> int:
        if stream.peek(index).content in cls.FIRST_CONTENTS:
            return FuncGetterNode.skip(
                stream, data_nodes.NameNode.skip(stream, index + 1)
            )

        return index

    def descendants(self):
        return iter((self.funcgetter_node, self.name_node))

    def parse_tree_descendants(self):
        return iter((self.funcgetter_node, self.name_node, ":"))


@starts_with(data_nodes.TableConstrNode)
class FuncGetterNode(AstNode):
    _D_T_ARGS = TokenDispatchTable(
        dict.fromkeys(
            data_nodes.TableConstrNode.FIRST_CONTENTS, data_nodes.TableConstrNode
        ),
        {"string": data_nodes.ConstNode},
    )

    FIRST_CONTENTS: NodeFirst = {"("}
    FIRST_NAMES: NodeFirst = {"string"}

    ERROR_NAME: str = "function call"

    __slots__ = ("arg",)

    def __init__(
        self,
        arg: list[data_nodes.ExpNode]
        | data_nodes.TableConstrNode
        | data_nodes.ConstNode,
    ):
        self.arg = arg

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        if (node_type := cls._D_T_ARGS[stream.peek()]) is not None:
            arg = node_type.from_tokens(stream)
        else:
            # skip (
            err_name = next(stream).content

            arg = list(parse_node_list(stream, data_nodes.ExpNode))
            if arg:
                err_name = arg[-1].ERROR_NAME

            parse_terminal(stream, ")", err_name)

        return cls(arg)

    @classmethod
    def skip(cls, stream: BufferedTokenStream, index: int = 0) -> int:
        t = stream.peek(index)
        if t.name in cls.FIRST_NAMES:
            return index + 1

        elif t.content == "(":
            return skip_parenthesis(stream, "(", ")", index)

        return data_nodes.TableConstrNode.skip(stream, index)

    def descendants(self):
        if isinstance(self.arg, list):
            return reversed(self.arg)

        return iter((self.arg,))

    def parse_tree_descendants(self):
        if isinstance(self.arg, list):
            return chain((")",), iter_sep(reversed(self.arg)), ("(",))

        return iter((self.arg,))
