from __future__ import annotations
from typing import Self
from itertools import chain

from lua.lua_ast.parsing import (
    Parsable,
    parsable_starts_with,
    LuaParser,
)
from lua.lua_ast.runtime_routines import iter_sep
from lua.lua_ast.ast_nodes.base_nodes import AstNode

import lua.lua_ast.ast_nodes.nodes.data_nodes as data_nodes
import lua.lua_ast.ast_nodes.nodes.statement_nodes as statement_nodes


class FuncBodyNode(AstNode, Parsable):
    # vararg if it exists should be the last element of args_node_list
    __slots__ = "args_node_list", "block_node"

    def __init__(
        self,
        args_node_list: list[data_nodes.NameNode | data_nodes.VarargNode],
        block_node: statement_nodes.BlockNode,
    ):
        self.args_node_list = args_node_list
        self.block_node = block_node

    def descendants(self):
        return chain(reversed(self.args_node_list), (self.block_node,))

    def parse_tree_descendants(self):
        return chain(
            ("end", self.block_node, ")"),
            iter_sep(reversed(self.args_node_list)),
            ("(",),
        )

    PARSABLE_FIRST_TOKEN_CONTENTS = {"("}
    PARSABLE_ERROR_NAME = "function body"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        # skip (
        err_name = next(stream).content
        # args_node_list presents
        args_node_list: list[data_nodes.NameNode | data_nodes.VarargNode] = []

        if data_nodes.NameNode.parsable_presented_in_stream(stream):
            args_node_list.extend(parser.parse_list(data_nodes.NameNode))

            if stream.peek().content == ",":
                args_node_list.append(
                    parser.parse_parsable(
                        data_nodes.VarargNode,
                        next(stream).content,
                        True,
                        f"{data_nodes.NameNode.PARSABLE_ERROR_NAME} or {data_nodes.VarargNode.PARSABLE_ERROR_NAME}",
                    )
                )

            err_name = args_node_list[-1].PARSABLE_ERROR_NAME

        elif data_nodes.VarargNode.parsable_presented_in_stream(stream):
            args_node_list.append(parser.parse_parsable(data_nodes.VarargNode))
            err_name = args_node_list[-1].PARSABLE_ERROR_NAME

        (block_node,) = parser.parse_simple_rule(
            (")", statement_nodes.BlockNode, "end"), err_name
        )

        return cls(args_node_list, block_node)


@parsable_starts_with(data_nodes.NameNode)
class FuncNameNode(AstNode, Parsable):
    __slots__ = "name_node_list", "method_name_node"

    # name_node_list always has at least one name
    def __init__(
        self,
        name_node_list: list[data_nodes.NameNode],
        method_name_node: data_nodes.NameNode | None,
    ):
        self.name_node_list = name_node_list
        self.method_name_node = method_name_node

    def descendants(self):
        g = reversed(self.name_node_list)
        return (
            g if self.method_name_node is None else chain((self.method_name_node,), g)
        )

    def parse_tree_descendants(self):
        g = iter_sep(reversed(self.name_node_list), ".")
        return (
            g
            if self.method_name_node is None
            else chain((self.method_name_node, ":"), g)
        )

    PARSABLE_ERROR_NAME = "function name"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        name_node_list = list(parser.parse_list(data_nodes.NameNode, {"."}))

        # parse [':' Name]
        stream = parser.token_stream
        method_name_node = None
        if stream.peek().content == ":":
            method_name_node = parser.parse_parsable(
                data_nodes.NameNode, next(stream).content, True
            )

        return cls(name_node_list, method_name_node)
