from __future__ import annotations
from collections.abc import Sequence

from lua.lexer import BufferedTokenStream
from lua.ast_nodes.base_nodes import AstNode, starts_with
from lua.parsing_routines import (
    TokenDispatchTable,
    parse_node_list,
    parse_simple_rule,
    parse_node,
)
from lua.runtime_routines import iter_sep

import lua.ast_nodes.nodes.data_nodes as data_nodes
import lua.ast_nodes.nodes.statement_nodes as statement_nodes


class FuncBodyNode(AstNode):
    FIRST_CONTENTS = {"("}

    __slots__ = "args_node_list", "block_node"

    # vararg if it exists should be the last element of args_node_list
    def __init__(
        self,
        args_node_list: list[data_nodes.NameNode | data_nodes.VarargNode],
        block_node: statement_nodes.BlockNode,
    ):
        self.args_node_list = args_node_list
        self.block_node = block_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        # skip (
        err_name = next(stream).content
        # args_node_list presents
        args_node_list: list[data_nodes.NameNode | data_nodes.VarargNode] = []

        if data_nodes.NameNode.presented_in_stream(stream):
            args_node_list.extend(parse_node_list(stream, data_nodes.NameNode))

            if stream.peek().content == ",":
                args_node_list.append(
                    parse_node(
                        stream,
                        data_nodes.VarargNode,
                        next(stream).content,
                        f"{data_nodes.NameNode.ERROR_NAME} or {data_nodes.VarargNode.ERROR_NAME}",
                    )
                )

            err_name = args_node_list[-1].ERROR_NAME

        elif data_nodes.VarargNode.presented_in_stream(stream):
            args_node_list.append(data_nodes.VarargNode.from_tokens(stream))
            err_name = args_node_list[-1].ERROR_NAME

        (block_node,) = parse_simple_rule(
            stream, (")", statement_nodes.BlockNode, "end"), err_name
        )

        return cls(args_node_list, block_node)

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return "(", *iter_sep(self.args_node_list), ")", self.block_node, "end"


@starts_with(data_nodes.NameNode)
class FuncNameNode(AstNode):
    ERROR_NAME = "function name"

    __slots__ = "name_node_list", "method_name_node"

    # name_node_list always has at least one name
    def __init__(
        self,
        name_node_list: list[data_nodes.NameNode],
        method_name_node: data_nodes.NameNode | None,
    ):
        self.name_node_list = name_node_list
        self.method_name_node = method_name_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        name_node_list = list(parse_node_list(stream, data_nodes.NameNode, {"."}))

        # parse [':' Name]
        method_name_node = None
        if stream.peek().content == ":":
            method_name_node = parse_node(
                stream, data_nodes.NameNode, next(stream).content
            )

        return cls(name_node_list, method_name_node)

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        if self.method_name_node is None:
            return (*iter_sep(self.name_node_list, "."),)

        return *iter_sep(self.name_node_list, "."), ":", self.method_name_node
