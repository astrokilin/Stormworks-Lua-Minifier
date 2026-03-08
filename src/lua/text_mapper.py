from bisect import bisect
from dataclasses import dataclass
from itertools import islice

from lua.lua_ast.ast_nodes.base_nodes import AstNode
from lua.lua_ast.lexer import LuaLexer


class TextMapper:
    """Maps one text chunks into another"""

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
        this_NodeInfo = TextMapper._NodeInfo(
            node.start_index, node.end_index, new_text_end, new_text_end
        )

        for n in node.parse_tree_descendants():
            if isinstance(n, str):
                if LuaLexer.is_concat(new_text_parts[-1][-1], n[0]):
                    this_NodeInfo.new_text_end += 1
                    new_text_parts.append(" ")
                    pos_list.append(this_NodeInfo.new_text_end)
                    info_list.append(empty_spot_val)

                this_NodeInfo.new_text_end += len(n)
                new_text_parts.append(n)
                pos_list.append(this_NodeInfo.new_text_end)
                info_list.append(this_NodeInfo)

            else:
                this_NodeInfo.new_text_end = TextMapper.__process_node(
                    new_text_parts,
                    pos_list,
                    info_list,
                    this_NodeInfo.new_text_end,
                    n,
                )

        return this_NodeInfo.new_text_end

    __slots__ = "text", "__pos_list", "__info_list"

    def __init__(self, node: AstNode):
        new_text_parts: list[str] = [";"]
        pos_list: list[int] = [0]
        info_list: list[TextMapper._NodeInfo] = []

        TextMapper.__process_node(new_text_parts, pos_list, info_list, 0, node)

        self.__pos_list = pos_list
        self.__info_list = info_list
        self.text = "".join(islice(new_text_parts, 1, None))

    def map(self, pos: int) -> tuple[int, int, int, int]:
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
