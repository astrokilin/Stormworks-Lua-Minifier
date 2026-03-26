from bisect import bisect
from dataclasses import dataclass
from itertools import islice, chain

from lua.lua_ast.ast_nodes.base_nodes import AstNode
from lua.lua_ast.lexer import LuaLexer


class TextMapper:
    """
    Creates a text and positions mapping from ast
    Fields:
        text - resulting text after ast traversal
    """

    @dataclass(slots=True)
    class _NodeInfo:
        orig_text_start: int
        orig_text_end: int
        new_text_start: int
        new_text_end: int

    @staticmethod
    def __process_node(
        new_text_parts: list[str],
        pos_list: list[int],
        info_list: list[_NodeInfo],
        new_text_end: int,
        node: AstNode,
        empty_spot_val: _NodeInfo = _NodeInfo(0, 0, 0, 0),
    ) -> int:
        """DFS preorder traversal of parse-tree to construct text, and locations mapping"""

        this_node_info = TextMapper._NodeInfo(
            node.start_index, node.end_index, new_text_end, new_text_end
        )

        # ugly skip of first space in sentence
        itr = node.parse_tree_descendants()
        n = next(itr, None)
        if n is None:
            return new_text_end

        if isinstance(n, str) and LuaLexer.is_concat(new_text_parts[-1][-1], n[0]):
            this_node_info.new_text_start += 1

        for n in chain((n,), itr):
            if isinstance(n, str):
                if LuaLexer.is_concat(new_text_parts[-1][-1], n[0]):
                    this_node_info.new_text_end += 1
                    new_text_parts.append(" ")
                    pos_list.append(this_node_info.new_text_end)
                    info_list.append(empty_spot_val)

                this_node_info.new_text_end += len(n)
                new_text_parts.append(n)
                pos_list.append(this_node_info.new_text_end)
                info_list.append(this_node_info)

            else:
                this_node_info.new_text_end = TextMapper.__process_node(
                    new_text_parts,
                    pos_list,
                    info_list,
                    this_node_info.new_text_end,
                    n,
                )

        return this_node_info.new_text_end

    __slots__ = "text", "__pos_list", "__info_list"

    def __init__(self, node: AstNode):
        new_text_parts: list[str] = [";"]
        pos_list: list[int] = [0]
        info_list: list[TextMapper._NodeInfo] = []

        TextMapper.__process_node(new_text_parts, pos_list, info_list, 0, node)

        pos_list.pop()
        self.__pos_list = pos_list
        self.__info_list = info_list
        self.text = "".join(islice(new_text_parts, 1, None))

    def map(self, pos: int) -> tuple[int, int, int, int]:
        """Takes position in text, constructed by ast traversing, returns source-result mapping"""
        if not self.__info_list:
            return (0, 0, 0, 0)

        index = bisect(self.__pos_list, pos)
        index = index - 1 if index > 0 else 0

        info = self.__info_list[index]
        return (
            info.orig_text_start,
            info.orig_text_end,
            info.new_text_start,
            info.new_text_end,
        )
